"""Ouvre une seule page de l'app dans une fenetre autonome, sans passer par le
login ni la fenetre principale - pour iterer rapidement en modifiant une page
et en relancant juste ce script (bien plus rapide que l'app complete ou l'exe).

Usage (depuis la racine du depot) :
        venv\\Scripts\\python.exe outils\\voir_page.py rapports
        venv\\Scripts\\python.exe outils\\voir_page.py indicateurs
        (nom du fichier dans app/views/, sans "_page.py")
"""
import os
import sys
import inspect
import importlib
# Outil deplace sous outils/ (racine du depot = un niveau au-dessus) : sans ce chemin
# explicite, "from app..." echoue quand ce script est lance directement, Python
# resolvant les imports depuis le dossier du script et non depuis le dossier courant.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.user import User

if len(sys.argv) != 2:
    print("Usage (depuis la racine du depot) : python outils/voir_page.py <nom_page>")
    print("Pages disponibles :")
    for nom in sorted(os.listdir("app/views")):
        if nom.endswith("_page.py"):
            print(" -", nom.removesuffix("_page.py"))
    sys.exit(1)

nom_page = sys.argv[1]
nom_module = f"app.views.{nom_page}_page"
nom_classe = "".join(mot.capitalize() for mot in nom_page.split("_")) + "Page"

module = importlib.import_module(nom_module)
classe_page = getattr(module, nom_classe)

app = QApplication(sys.argv)

# Depuis l'ajout du controle d'acces par role, la plupart des pages exigent
# l'utilisateur connecte (pour savoir quelles actions d'ecriture activer) :
# on se connecte avec le compte admin de la base si le constructeur en a besoin.
if len(inspect.signature(classe_page.__init__).parameters) > 1:
    session = SessionLocal()
    utilisateur_test = session.query(User).options(joinedload(User.role)).filter_by(username="admin").first()
    session.close()
    args_page = (utilisateur_test,)
else:
    args_page = ()
# Meme correctif que main.py, contre le theme sombre Windows sur les QMessageBox
app.setStyleSheet("""
    QMessageBox { background-color: white; }
    QMessageBox QLabel { color: black; }
    QMessageBox QPushButton { color: black; background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; padding: 4px 14px; }
""")
fenetre = classe_page(*args_page)
fenetre.setWindowTitle(f"Apercu autonome — {nom_classe}")
fenetre.resize(1100, 750)
fenetre.show()
app.exec()
