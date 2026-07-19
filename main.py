import os
import sys
import traceback
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from app.views.login_window import LoginWindow
from app.views.main_window import MainWindow
from app.database import SessionLocal
from app.models.user import User
from app.utils.enter_focus_filter import FiltreEntreeChampSuivant
from app.services.scheduler import demarrer_scheduler
from PySide6.QtGui import QIcon

MODE_TEST_SANS_LOGIN = False  # Mettre à True pour ignorer l'écran de connexion et se connecter automatiquement avec l'utilisateur "admin"

# En exécutable PyInstaller, __file__ pointe vers le dossier d'extraction
# temporaire, pas vers le projet — l'icône doit alors être cherchée à côté
# de l'exécutable plutôt que relativement au code source.
if getattr(sys, "frozen", False):
    _RACINE_PROJET = os.path.dirname(sys.executable)
else:
    _RACINE_PROJET = os.path.dirname(os.path.abspath(__file__))

# En mode windowed (pas de console), une exception non interceptee dans un
# slot Qt (ex. construction paresseuse d'une page) ne s'affiche nulle part :
# l'app reste plantee silencieusement sur "Chargement...". On la journalise
# et on previent l'utilisateur au lieu de la laisser disparaitre.
def _gestionnaire_exceptions(exc_type, exc_value, exc_tb):
    chemin_log = os.path.join(_RACINE_PROJET, "erreur.log")
    with open(chemin_log, "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    QMessageBox.critical(
        None, "Erreur inattendue",
        f"Une erreur est survenue :\n{exc_value}\n\nDétails dans erreur.log"
    )

sys.excepthook = _gestionnaire_exceptions

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(os.path.join(_RACINE_PROJET, "assets", "logo.png")))
app.setStyleSheet("""
    QWidget { color: #2c3e50; }
    QMessageBox { background-color: white; }
    QLineEdit, QDoubleSpinBox, QComboBox { color: #2c3e50; background-color: white; }
""")

filtre_entree = FiltreEntreeChampSuivant()
app.installEventFilter(filtre_entree)

scheduler = demarrer_scheduler()

if MODE_TEST_SANS_LOGIN:
    session = SessionLocal()
    utilisateur_test = session.query(User).filter_by(username="admin").first()
    session.close()
    fenetre = MainWindow(utilisateur_test)
else:
    fenetre = LoginWindow()

fenetre.show()
sys.exit(app.exec())