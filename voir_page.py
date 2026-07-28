"""Ouvre une seule page de l'app dans une fenetre autonome, sans passer par le
login ni la fenetre principale - pour iterer rapidement en modifiant une page
et en relancant juste ce script (bien plus rapide que l'app complete ou l'exe).

Usage : venv\\Scripts\\python.exe voir_page.py rapports
        venv\\Scripts\\python.exe voir_page.py indicateurs
        (nom du fichier dans app/views/, sans "_page.py")
"""
import sys
import importlib
from PySide6.QtWidgets import QApplication

if len(sys.argv) != 2:
    print("Usage : python voir_page.py <nom_page>")
    print("Pages disponibles :")
    import os
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
# Meme correctif que main.py, contre le theme sombre Windows sur les QMessageBox
app.setStyleSheet("""
    QMessageBox { background-color: white; }
    QMessageBox QLabel { color: black; }
    QMessageBox QPushButton { color: black; background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; padding: 4px 14px; }
""")
fenetre = classe_page()
fenetre.setWindowTitle(f"Apercu autonome — {nom_classe}")
fenetre.resize(1100, 750)
fenetre.show()
app.exec()
