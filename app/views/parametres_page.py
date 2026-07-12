import os
import re
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QMessageBox, QFileDialog, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import bcrypt
from dotenv import find_dotenv, set_key
from app.database import SessionLocal
from app.models.user import User
from app.services.historique import enregistrer as enregistrer_historique


class ParametresPage(QWidget):
    def __init__(self, utilisateur_connecte):
        super().__init__()
        self.utilisateur_connecte = utilisateur_connecte
        self.setStyleSheet("background-color: #f4f6f8;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        titre = QLabel("Paramètres")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(titre)

        layout.addWidget(self._bloc_mon_compte())
        layout.addWidget(self._bloc_notifications())
        layout.addWidget(self._bloc_sauvegarde())
        layout.addStretch()

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

    def _style_champ(self):
        return """
            QLineEdit { color: #2c3e50; background-color: white; border: 1px solid #ccc; border-radius: 6px; padding: 8px; }
            QLineEdit:focus { border: 1px solid #1a5276; }
        """

    def _style_bouton(self, couleur, couleur_hover):
        return f"""
            QPushButton {{ background-color: {couleur}; color: white; border-radius: 6px; padding: 9px 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {couleur_hover}; }}
        """

    # --- Bloc 1 : Mon compte ---
    def _bloc_mon_compte(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        titre = QLabel(f"Mon compte — {self.utilisateur_connecte.username}")
        titre.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout.addWidget(titre)

        layout.addWidget(QLabel("Mot de passe actuel"))
        self.champ_mdp_actuel = QLineEdit()
        self.champ_mdp_actuel.setEchoMode(QLineEdit.Password)
        self.champ_mdp_actuel.setStyleSheet(self._style_champ())
        layout.addWidget(self.champ_mdp_actuel)

        layout.addWidget(QLabel("Nouveau mot de passe"))
        self.champ_mdp_nouveau = QLineEdit()
        self.champ_mdp_nouveau.setEchoMode(QLineEdit.Password)
        self.champ_mdp_nouveau.setStyleSheet(self._style_champ())
        layout.addWidget(self.champ_mdp_nouveau)

        layout.addWidget(QLabel("Confirmer le nouveau mot de passe"))
        self.champ_mdp_confirmation = QLineEdit()
        self.champ_mdp_confirmation.setEchoMode(QLineEdit.Password)
        self.champ_mdp_confirmation.setStyleSheet(self._style_champ())
        layout.addWidget(self.champ_mdp_confirmation)

        self.label_statut_mdp = QLabel("")
        self.label_statut_mdp.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.label_statut_mdp)

        bouton = QPushButton("Changer le mot de passe")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        bouton.clicked.connect(self._changer_mot_de_passe)
        layout.addWidget(bouton)

        return bloc

    def _changer_mot_de_passe(self):
        actuel = self.champ_mdp_actuel.text()
        nouveau = self.champ_mdp_nouveau.text()
        confirmation = self.champ_mdp_confirmation.text()

        if not actuel or not nouveau or not confirmation:
            self.label_statut_mdp.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_mdp.setText("Tous les champs sont obligatoires.")
            return

        if nouveau != confirmation:
            self.label_statut_mdp.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_mdp.setText("Les deux nouveaux mots de passe ne correspondent pas.")
            return

        if len(nouveau) < 6:
            self.label_statut_mdp.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_mdp.setText("Le nouveau mot de passe doit contenir au moins 6 caractères.")
            return

        session = SessionLocal()
        user = session.query(User).filter_by(id=self.utilisateur_connecte.id).first()

        if not bcrypt.checkpw(actuel.encode("utf-8"), user.password_hash.encode("utf-8")):
            session.close()
            self.label_statut_mdp.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_mdp.setText("Mot de passe actuel incorrect.")
            return

        user.password_hash = bcrypt.hashpw(nouveau.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        enregistrer_historique(
            session, self.utilisateur_connecte, "Changement de mot de passe", "Utilisateur", user.id,
            f"« {user.username} » a changé son propre mot de passe."
        )

        session.commit()
        session.close()

        self.champ_mdp_actuel.clear()
        self.champ_mdp_nouveau.clear()
        self.champ_mdp_confirmation.clear()

        self.label_statut_mdp.setStyleSheet("color: #27ae60; font-size: 12px;")
        self.label_statut_mdp.setText("Mot de passe changé avec succès.")

    # --- Bloc 2 : Notifications par email ---
    def _bloc_notifications(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        titre = QLabel("Notifications par email")
        titre.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout.addWidget(titre)

        description = QLabel(
            "Adresse(s) qui reçoivent le rapport météorologique automatique de 6h ainsi que "
            "les rapports envoyés manuellement depuis la page Rapports. "
            "Plusieurs adresses peuvent être séparées par une virgule."
        )
        description.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(QLabel("Destinataire(s)"))
        self.champ_destinataires = QLineEdit()
        self.champ_destinataires.setPlaceholderText("exemple@domaine.com, autre@domaine.com")
        self.champ_destinataires.setText(os.getenv("SMTP_DESTINATAIRES", ""))
        self.champ_destinataires.setStyleSheet(self._style_champ())
        layout.addWidget(self.champ_destinataires)

        self.label_statut_email = QLabel("")
        self.label_statut_email.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.label_statut_email)

        bouton = QPushButton("Enregistrer le(s) destinataire(s)")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        bouton.clicked.connect(self._enregistrer_destinataires)
        layout.addWidget(bouton)

        return bloc

    def _enregistrer_destinataires(self):
        adresses = [a.strip() for a in self.champ_destinataires.text().split(",") if a.strip()]

        if not adresses:
            self.label_statut_email.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_email.setText("Indiquez au moins une adresse email.")
            return

        motif_email = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        invalides = [a for a in adresses if not motif_email.match(a)]
        if invalides:
            self.label_statut_email.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_email.setText(f"Adresse(s) invalide(s) : {', '.join(invalides)}")
            return

        valeur_normalisee = ",".join(adresses)

        chemin_env = find_dotenv()
        if not chemin_env:
            self.label_statut_email.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_email.setText("Fichier .env introuvable.")
            return

        set_key(chemin_env, "SMTP_DESTINATAIRES", valeur_normalisee)
        os.environ["SMTP_DESTINATAIRES"] = valeur_normalisee
        self.champ_destinataires.setText(valeur_normalisee)

        self.label_statut_email.setStyleSheet("color: #27ae60; font-size: 12px;")
        self.label_statut_email.setText("Destinataire(s) enregistré(s) avec succès.")

    # --- Bloc 3 : Sauvegarde de la base de données ---
    def _bloc_sauvegarde(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        titre = QLabel("Sauvegarde de la base de données")
        titre.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout.addWidget(titre)

        description = QLabel(
            "Génère une copie complète de la base (stations, mesures, indicateurs, utilisateurs) "
            "sous forme de fichier .sql, à conserver en lieu sûr."
        )
        description.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.label_statut_sauvegarde = QLabel("")
        self.label_statut_sauvegarde.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.label_statut_sauvegarde)

        bouton = QPushButton("💾  Créer une sauvegarde")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setStyleSheet(self._style_bouton("#27ae60", "#1e8449"))
        bouton.clicked.connect(self._creer_sauvegarde)
        layout.addWidget(bouton)

        return bloc

    def _trouver_pg_dump(self):
        # Priorité : variable d'environnement si définie
        chemin_env = os.getenv("PG_DUMP_PATH")
        if chemin_env and os.path.exists(chemin_env):
            return chemin_env

        # Recherche dans les emplacements standards d'installation Windows
        base = r"C:\Program Files\PostgreSQL"
        if os.path.isdir(base):
            for version in sorted(os.listdir(base), reverse=True):
                chemin_possible = os.path.join(base, version, "bin", "pg_dump.exe")
                if os.path.exists(chemin_possible):
                    return chemin_possible

        return None

    def _creer_sauvegarde(self):
        pg_dump = self._trouver_pg_dump()
        if not pg_dump:
            QMessageBox.critical(
                self, "pg_dump introuvable",
                "L'outil pg_dump.exe n'a pas été trouvé automatiquement.\n\n"
                "Ajoute une ligne PG_DUMP_PATH=chemin\\vers\\pg_dump.exe dans le fichier .env, "
                "en indiquant le chemin exact (généralement dans le dossier bin de ton installation PostgreSQL)."
            )
            return

        database_url = os.getenv("DATABASE_URL", "")
        correspondance = re.match(
            r"postgresql\+?\w*://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)",
            database_url
        )
        if not correspondance:
            QMessageBox.critical(self, "Erreur", "Impossible de lire les informations de connexion depuis .env.")
            return

        utilisateur_db, mot_de_passe_db, hote, port, nom_base = correspondance.groups()
        port = port or "5432"

        nom_fichier_defaut = f"sauvegarde_ormvag_{datetime.now().strftime('%Y%m%d_%H%M')}.sql"
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde", nom_fichier_defaut, "Fichier SQL (*.sql)")
        if not chemin:
            return

        self.label_statut_sauvegarde.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.label_statut_sauvegarde.setText("Sauvegarde en cours...")

        environnement = os.environ.copy()
        environnement["PGPASSWORD"] = mot_de_passe_db

        try:
            resultat = subprocess.run(
                [pg_dump, "-h", hote, "-p", port, "-U", utilisateur_db, "-F", "p", "-f", chemin, nom_base],
                env=environnement, capture_output=True, text=True, timeout=120
            )

            if resultat.returncode == 0:
                self.label_statut_sauvegarde.setStyleSheet("color: #27ae60; font-size: 12px;")
                self.label_statut_sauvegarde.setText(f"Sauvegarde créée : {chemin}")
                QMessageBox.information(self, "Sauvegarde réussie", f"Fichier enregistré :\n{chemin}")
            else:
                self.label_statut_sauvegarde.setStyleSheet("color: #c0392b; font-size: 12px;")
                self.label_statut_sauvegarde.setText("Échec de la sauvegarde.")
                QMessageBox.critical(self, "Erreur", f"pg_dump a échoué :\n{resultat.stderr}")

        except Exception as e:
            self.label_statut_sauvegarde.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_sauvegarde.setText("Erreur lors de la sauvegarde.")
            QMessageBox.critical(self, "Erreur", str(e))