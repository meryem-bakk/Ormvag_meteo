import sys
from PySide6.QtWidgets import QApplication
from app.views.login_window import LoginWindow
from app.views.main_window import MainWindow
from app.database import SessionLocal
from app.models.user import User
from app.utils.enter_focus_filter import FiltreEntreeChampSuivant
from app.services.scheduler import demarrer_scheduler

MODE_TEST_SANS_LOGIN = True  # Mettre à True pour ignorer l'écran de connexion et se connecter automatiquement avec l'utilisateur "admin"

app = QApplication(sys.argv)
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