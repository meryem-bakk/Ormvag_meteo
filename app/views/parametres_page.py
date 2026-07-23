import os
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
import bcrypt
from dotenv import find_dotenv, set_key
from app.database import SessionLocal
from app.models.user import User
from app.services.historique import enregistrer as enregistrer_historique
from app.services.sauvegarde import trouver_pg_dump, executer_pg_dump
from app.utils.theme import COULEURS, titre_section


class ParametresPage(QWidget):
    def __init__(self, utilisateur_connecte):
        super().__init__()
        self.utilisateur_connecte = utilisateur_connecte
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        titre = QLabel("Paramètres")
        titre.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COULEURS['texte']};")
        layout.addWidget(titre)

        layout.addLayout(self._bloc_mon_compte())
        layout.addLayout(self._bloc_notifications())
        layout.addLayout(self._bloc_sauvegarde())
        layout.addStretch()

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
        bloc, _ = titre_section(f"Mon compte — {self.utilisateur_connecte.username}")
        largeur_champ = 360

        bloc.addWidget(QLabel("Mot de passe actuel"))
        self.champ_mdp_actuel = QLineEdit()
        self.champ_mdp_actuel.setEchoMode(QLineEdit.Password)
        self.champ_mdp_actuel.setMaximumWidth(largeur_champ)
        self.champ_mdp_actuel.setStyleSheet(self._style_champ())
        bloc.addWidget(self.champ_mdp_actuel)

        bloc.addWidget(QLabel("Nouveau mot de passe"))
        self.champ_mdp_nouveau = QLineEdit()
        self.champ_mdp_nouveau.setEchoMode(QLineEdit.Password)
        self.champ_mdp_nouveau.setMaximumWidth(largeur_champ)
        self.champ_mdp_nouveau.setStyleSheet(self._style_champ())
        bloc.addWidget(self.champ_mdp_nouveau)

        bloc.addWidget(QLabel("Confirmer le nouveau mot de passe"))
        self.champ_mdp_confirmation = QLineEdit()
        self.champ_mdp_confirmation.setEchoMode(QLineEdit.Password)
        self.champ_mdp_confirmation.setMaximumWidth(largeur_champ)
        self.champ_mdp_confirmation.setStyleSheet(self._style_champ())
        bloc.addWidget(self.champ_mdp_confirmation)

        self.label_statut_mdp = QLabel("")
        self.label_statut_mdp.setStyleSheet("font-size: 12px;")
        bloc.addWidget(self.label_statut_mdp)

        bouton = QPushButton("Changer le mot de passe")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setMaximumWidth(largeur_champ)
        bouton.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        bouton.clicked.connect(self._changer_mot_de_passe)
        bloc.addWidget(bouton)

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
        bloc, _ = titre_section("Notifications par email")
        largeur_champ = 420

        description = QLabel(
            "Adresse(s) qui reçoivent le rapport météorologique automatique de 6h ainsi que "
            "les rapports envoyés manuellement depuis la page Rapports. "
            "Plusieurs adresses peuvent être séparées par une virgule."
        )
        description.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 12px;")
        description.setWordWrap(True)
        bloc.addWidget(description)

        bloc.addWidget(QLabel("Destinataire(s)"))
        self.champ_destinataires = QLineEdit()
        self.champ_destinataires.setPlaceholderText("exemple@domaine.com, autre@domaine.com")
        self.champ_destinataires.setText(os.getenv("SMTP_DESTINATAIRES", ""))
        self.champ_destinataires.setMaximumWidth(largeur_champ)
        self.champ_destinataires.setStyleSheet(self._style_champ())
        bloc.addWidget(self.champ_destinataires)

        self.label_statut_email = QLabel("")
        self.label_statut_email.setStyleSheet("font-size: 12px;")
        bloc.addWidget(self.label_statut_email)

        bouton = QPushButton("Enregistrer le(s) destinataire(s)")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setMaximumWidth(largeur_champ)
        bouton.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        bouton.clicked.connect(self._enregistrer_destinataires)
        bloc.addWidget(bouton)

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
        bloc, _ = titre_section("Sauvegarde de la base de données")

        description = QLabel(
            "Une sauvegarde automatique est déjà générée chaque jour à 8h00 dans le dossier "
            "« Sauvegardes/ » (les 14 plus récentes sont conservées, les plus anciennes supprimées). "
            "Le bouton ci-dessous permet en plus de créer une sauvegarde manuelle à l'emplacement de ton choix."
        )
        description.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 12px;")
        description.setWordWrap(True)
        bloc.addWidget(description)

        self.label_statut_sauvegarde = QLabel("")
        self.label_statut_sauvegarde.setStyleSheet("font-size: 12px;")
        bloc.addWidget(self.label_statut_sauvegarde)

        ligne_bouton = QHBoxLayout()
        bouton = QPushButton("Créer une sauvegarde")
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.setStyleSheet(self._style_bouton("#27ae60", "#1e8449"))
        bouton.clicked.connect(self._creer_sauvegarde)
        ligne_bouton.addWidget(bouton)
        ligne_bouton.addStretch()
        bloc.addLayout(ligne_bouton)

        return bloc

    def _creer_sauvegarde(self):
        if not trouver_pg_dump():
            QMessageBox.critical(
                self, "pg_dump introuvable",
                "L'outil pg_dump.exe n'a pas été trouvé automatiquement.\n\n"
                "Ajoute une ligne PG_DUMP_PATH=chemin\\vers\\pg_dump.exe dans le fichier .env, "
                "en indiquant le chemin exact (généralement dans le dossier bin de ton installation PostgreSQL)."
            )
            return

        nom_fichier_defaut = f"sauvegarde_ormvag_{datetime.now().strftime('%Y%m%d_%H%M')}.sql"
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde", nom_fichier_defaut, "Fichier SQL (*.sql)")
        if not chemin:
            return

        self.label_statut_sauvegarde.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.label_statut_sauvegarde.setText("Sauvegarde en cours...")

        succes, message = executer_pg_dump(chemin)

        if succes:
            self.label_statut_sauvegarde.setStyleSheet("color: #27ae60; font-size: 12px;")
            self.label_statut_sauvegarde.setText(f"Sauvegarde créée : {chemin}")
            QMessageBox.information(self, "Sauvegarde réussie", f"Fichier enregistré :\n{chemin}")
        else:
            self.label_statut_sauvegarde.setStyleSheet("color: #c0392b; font-size: 12px;")
            self.label_statut_sauvegarde.setText("Échec de la sauvegarde.")
            QMessageBox.critical(self, "Erreur", f"La sauvegarde a échoué :\n{message}")