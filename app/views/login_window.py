import bcrypt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from app.database import SessionLocal
from app.models.user import User
from app.views.main_window import MainWindow
from datetime import datetime


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ORMVAG Météo Manager - Connexion")
        self.resize(960, 560)
        self.setMinimumSize(760, 480)
        self._build_ui()

    def _build_ui(self):
        layout_principal = QHBoxLayout(self)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        # --- Panneau gauche : image/branding ---
        panneau_gauche = QFrame()
        panneau_gauche.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a5276, stop:1 #154360);
            }
        """)
        layout_gauche = QVBoxLayout(panneau_gauche)
        layout_gauche.setAlignment(Qt.AlignCenter)
        layout_gauche.setContentsMargins(40, 40, 40, 40)
        layout_gauche.setSpacing(16)

        icone = QLabel("🌦️")
        icone.setStyleSheet("font-size: 64px;")
        icone.setAlignment(Qt.AlignCenter)
        layout_gauche.addWidget(icone)

        titre_gauche = QLabel("ORMVAG\nMÉTÉO MANAGER")
        titre_gauche.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        titre_gauche.setAlignment(Qt.AlignCenter)
        layout_gauche.addWidget(titre_gauche)

        sous_titre_gauche = QLabel(
            "Gestion, traitement et valorisation\n"
            "des données météorologiques\n"
            "du périmètre du Gharb"
        )
        sous_titre_gauche.setStyleSheet("color: #cdd9e5; font-size: 13px;")
        sous_titre_gauche.setAlignment(Qt.AlignCenter)
        layout_gauche.addWidget(sous_titre_gauche)

        stats_rapides = QLabel("17 stations  •  Surveillance continue  •  Aide à la décision")
        stats_rapides.setStyleSheet("color: #85a9c4; font-size: 11px; margin-top: 20px;")
        stats_rapides.setAlignment(Qt.AlignCenter)
        layout_gauche.addWidget(stats_rapides)

        layout_principal.addWidget(panneau_gauche, stretch=1)

        # --- Panneau droit : formulaire de connexion ---
        panneau_droit = QFrame()
        panneau_droit.setStyleSheet("background-color: #f4f6f8;")
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setAlignment(Qt.AlignCenter)

        carte = QFrame()
        carte.setFixedWidth(340)
        carte.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
            }
        """)
        layout_carte = QVBoxLayout(carte)
        layout_carte.setContentsMargins(32, 32, 32, 32)
        layout_carte.setSpacing(12)

        titre = QLabel("Connexion")
        titre.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        layout_carte.addWidget(titre)

        sous_titre = QLabel("Accédez à votre espace de suivi météorologique")
        sous_titre.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-bottom: 8px;")
        sous_titre.setWordWrap(True)
        layout_carte.addWidget(sous_titre)

        label_utilisateur = QLabel("Nom d'utilisateur")
        label_utilisateur.setStyleSheet("color: #2c3e50; font-weight: 500; font-size: 12px;")
        layout_carte.addWidget(label_utilisateur)

        self.champ_utilisateur = QLineEdit()
        self.champ_utilisateur.setPlaceholderText("Entrez votre nom d'utilisateur")
        self.champ_utilisateur.setStyleSheet(self._style_champ())
        layout_carte.addWidget(self.champ_utilisateur)

        label_mdp = QLabel("Mot de passe")
        label_mdp.setStyleSheet("color: #2c3e50; font-weight: 500; font-size: 12px; margin-top: 4px;")
        layout_carte.addWidget(label_mdp)

        self.champ_mdp = QLineEdit()
        self.champ_mdp.setPlaceholderText("Entrez votre mot de passe")
        self.champ_mdp.setEchoMode(QLineEdit.Password)
        self.champ_mdp.setStyleSheet(self._style_champ())
        layout_carte.addWidget(self.champ_mdp)

        self.case_souvenir = QCheckBox("Se souvenir de moi")
        self.case_souvenir.setStyleSheet("color: #2c3e50; margin-top: 4px;")
        layout_carte.addWidget(self.case_souvenir)

        self.label_erreur = QLabel("")
        self.label_erreur.setStyleSheet("color: #c0392b; font-size: 12px;")
        self.label_erreur.setWordWrap(True)
        layout_carte.addWidget(self.label_erreur)

        bouton_connexion = QPushButton("Se connecter")
        bouton_connexion.setCursor(Qt.PointingHandCursor)
        bouton_connexion.setMinimumHeight(40)
        bouton_connexion.setStyleSheet("""
            QPushButton {
                background-color: #1a5276; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
                margin-top: 8px;
            }
            QPushButton:hover { background-color: #154360; }
        """)
        bouton_connexion.clicked.connect(self._tenter_connexion)
        layout_carte.addWidget(bouton_connexion)

        footer = QLabel("© ORMVAG - Tous droits réservés")
        footer.setStyleSheet("color: #bdc3c7; font-size: 10px; margin-top: 16px;")
        footer.setAlignment(Qt.AlignCenter)
        layout_carte.addWidget(footer)

        layout_droit.addWidget(carte)
        layout_principal.addWidget(panneau_droit, stretch=1)

    def _style_champ(self):
        return """
            QLineEdit {
                border: 1px solid #ccc; border-radius: 6px; padding: 9px;
                color: #2c3e50; background-color: white; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #1a5276; }
        """

    def _tenter_connexion(self):
        utilisateur = self.champ_utilisateur.text().strip()
        mdp = self.champ_mdp.text()

        if not utilisateur or not mdp:
            self.label_erreur.setText("Veuillez remplir tous les champs.")
            return

        session = SessionLocal()
        user = session.query(User).filter_by(username=utilisateur, actif=True).first()

        if user and bcrypt.checkpw(mdp.encode("utf-8"), user.password_hash.encode("utf-8")):
            user.derniere_connexion = datetime.now()
            session.commit()
            session.close()
            self.label_erreur.setText("")
            self.fenetre_principale = MainWindow(user)
            self.fenetre_principale.show()
            self.close()
        else:
            session.close()
            self.label_erreur.setText("Identifiant ou mot de passe incorrect.")