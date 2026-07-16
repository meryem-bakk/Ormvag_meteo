import os
import sys
from PySide6.QtWidgets import QApplication
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