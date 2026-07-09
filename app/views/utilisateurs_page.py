from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QFrame, QHeaderView, QMessageBox, QGraphicsDropShadowEffect, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import bcrypt
from app.database import SessionLocal
from app.models.user import User
from app.models.role import Role


class UtilisateursPage(QWidget):
    def __init__(self, utilisateur_connecte):
        super().__init__()
        self.utilisateur_connecte = utilisateur_connecte
        self.setStyleSheet("background-color: #f4f6f8;")
        self.user_en_edition_id = None
        self._build_ui()
        self._charger_roles_dans_combo()
        self._charger_utilisateurs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        titre = QLabel("Gestion des utilisateurs")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(titre)

        # --- Formulaire ---
        formulaire = QFrame()
        formulaire.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        formulaire.setGraphicsEffect(self._ombre_legere())
        layout_form_ext = QVBoxLayout(formulaire)
        layout_form_ext.setContentsMargins(20, 16, 20, 16)
        layout_form_ext.setSpacing(10)

        self.label_mode_form = QLabel("Ajouter un utilisateur")
        self.label_mode_form.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout_form_ext.addWidget(self.label_mode_form)

        style_champ = """
            QLineEdit, QComboBox {
                color: #2c3e50; background-color: white;
                border: 1px solid #ccc; border-radius: 6px; padding: 7px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #1a5276; }
        """
        style_label = "color: #7f8c8d; font-size: 11px; font-weight: 600;"

        grille = QGridLayout()
        grille.setHorizontalSpacing(14)
        grille.setVerticalSpacing(4)

        grille.addWidget(self._label(style_label, "NOM D'UTILISATEUR"), 0, 0)
        grille.addWidget(self._label(style_label, "NOM COMPLET"), 0, 1)
        grille.addWidget(self._label(style_label, "EMAIL"), 0, 2)
        grille.addWidget(self._label(style_label, "RÔLE"), 0, 3)
        grille.addWidget(self._label(style_label, "MOT DE PASSE"), 0, 4)

        self.champ_username = QLineEdit()
        self.champ_username.setPlaceholderText("ex : tech01")
        self.champ_username.setStyleSheet(style_champ)
        grille.addWidget(self.champ_username, 1, 0)

        self.champ_nom_complet = QLineEdit()
        self.champ_nom_complet.setPlaceholderText("ex : Ahmed Technicien")
        self.champ_nom_complet.setStyleSheet(style_champ)
        grille.addWidget(self.champ_nom_complet, 1, 1)

        self.champ_email = QLineEdit()
        self.champ_email.setPlaceholderText("ex : ahmed@ormvag.ma")
        self.champ_email.setStyleSheet(style_champ)
        grille.addWidget(self.champ_email, 1, 2)

        self.combo_role = QComboBox()
        self.combo_role.setStyleSheet(style_champ)
        grille.addWidget(self.combo_role, 1, 3)

        self.champ_mdp = QLineEdit()
        self.champ_mdp.setPlaceholderText("Laisser vide pour ne pas changer")
        self.champ_mdp.setEchoMode(QLineEdit.Password)
        self.champ_mdp.setStyleSheet(style_champ)
        grille.addWidget(self.champ_mdp, 1, 4)

        for col in range(5):
            grille.setColumnStretch(col, 1)

        layout_form_ext.addLayout(grille)

        self.case_actif = QCheckBox("Compte actif")
        self.case_actif.setChecked(True)
        self.case_actif.setStyleSheet("color: #2c3e50; margin-top: 4px;")
        layout_form_ext.addWidget(self.case_actif)

        layout_boutons_form = QHBoxLayout()
        layout_boutons_form.addStretch()

        self.bouton_annuler = QPushButton("Annuler")
        self.bouton_annuler.setCursor(Qt.PointingHandCursor)
        self.bouton_annuler.setStyleSheet(self._style_bouton("#95a5a6", "#7f8c8d"))
        self.bouton_annuler.clicked.connect(self._reinitialiser_formulaire)
        self.bouton_annuler.hide()
        layout_boutons_form.addWidget(self.bouton_annuler)

        self.bouton_valider = QPushButton("+ Ajouter l'utilisateur")
        self.bouton_valider.setCursor(Qt.PointingHandCursor)
        self.bouton_valider.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        self.bouton_valider.clicked.connect(self._valider_formulaire)
        layout_boutons_form.addWidget(self.bouton_valider)

        layout_form_ext.addLayout(layout_boutons_form)
        layout.addWidget(formulaire)

        # --- Actions sur sélection ---
        layout_actions = QHBoxLayout()
        layout_actions.addWidget(self._label("color: #7f8c8d; font-size: 12px;", "Sélectionne une ligne pour la modifier :"))
        layout_actions.addStretch()

        self.bouton_modifier = QPushButton("✎  Modifier")
        self.bouton_modifier.setCursor(Qt.PointingHandCursor)
        self.bouton_modifier.setStyleSheet(self._style_bouton("#e67e22", "#d35400"))
        self.bouton_modifier.clicked.connect(self._charger_dans_formulaire)
        layout_actions.addWidget(self.bouton_modifier)

        self.bouton_reinitialiser_mdp = QPushButton("🔑  Réinitialiser le mot de passe")
        self.bouton_reinitialiser_mdp.setCursor(Qt.PointingHandCursor)
        self.bouton_reinitialiser_mdp.setStyleSheet(self._style_bouton("#8e44ad", "#6c3483"))
        self.bouton_reinitialiser_mdp.clicked.connect(self._reinitialiser_mot_de_passe)
        layout_actions.addWidget(self.bouton_reinitialiser_mdp)

        layout.addLayout(layout_actions)

        # --- Tableau ---
        self.tableau = QTableWidget()
        self.tableau.setColumnCount(7)
        self.tableau.setHorizontalHeaderLabels(["ID", "Utilisateur", "Nom complet", "Rôle", "Statut", "Email", "Dernière connexion"])
        self.tableau.verticalHeader().setVisible(False)

        header = self.tableau.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)

        largeurs_colonnes = [40, 110, 160, 130, 90, 180, 140]
        for i, largeur in enumerate(largeurs_colonnes):
            self.tableau.setColumnWidth(i, largeur)

        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Nom complet s'étire pour combler l'espace
        self.tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableau.setSelectionMode(QTableWidget.SingleSelection)
        self.tableau.setAlternatingRowColors(True)
        self.tableau.verticalHeader().setDefaultSectionSize(34)
        self.tableau.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 10px; color: #2c3e50; gridline-color: #ecf0f1; border: none; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
            QTableWidget::item:selected { background-color: #d6eaf8; color: #1a5276; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 8px; border: none; font-weight: bold; }
        """)
        layout.addWidget(self.tableau)

    def _label(self, style, texte):
        label = QLabel(texte)
        label.setStyleSheet(style)
        return label

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

    def _style_bouton(self, couleur, couleur_hover):
        return f"""
            QPushButton {{ background-color: {couleur}; color: white; border-radius: 6px; padding: 9px 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {couleur_hover}; }}
        """

    def _charger_roles_dans_combo(self):
        session = SessionLocal()
        roles = session.query(Role).order_by(Role.nom).all()
        session.close()

        self.combo_role.clear()
        for role in roles:
            self.combo_role.addItem(role.nom, role.id)

    def _charger_utilisateurs(self):
        session = SessionLocal()
        utilisateurs = session.query(User).order_by(User.id).all()

        self.tableau.setRowCount(len(utilisateurs))
        for i, u in enumerate(utilisateurs):
            valeurs = [
                str(u.id),
                u.username,
                u.nom_complet or "—",
                u.role.nom if u.role else "—",
                "Actif" if u.actif else "Désactivé",
                u.email or "—",
                u.derniere_connexion.strftime("%d/%m/%Y %H:%M") if u.derniere_connexion else "Jamais connecté",
            ]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                if col == 4:
                    item.setForeground(QColor("#27ae60") if u.actif else QColor("#c0392b"))
                else:
                    item.setForeground(QColor("#2c3e50"))
                self.tableau.setItem(i, col, item)

        session.close()

    def _ligne_selectionnee(self):
        lignes = self.tableau.selectionModel().selectedRows()
        if not lignes:
            QMessageBox.information(self, "Aucune sélection", "Sélectionne d'abord un utilisateur dans le tableau.")
            return None
        return lignes[0].row()

    def _charger_dans_formulaire(self):
        ligne = self._ligne_selectionnee()
        if ligne is None:
            return

        user_id = int(self.tableau.item(ligne, 0).text())
        self.user_en_edition_id = user_id

        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()

        self.champ_username.setText(user.username)
        self.champ_nom_complet.setText(user.nom_complet or "")
        self.champ_email.setText(user.email or "")
        self.champ_mdp.clear()
        self.case_actif.setChecked(user.actif)

        index_role = self.combo_role.findData(user.role_id)
        if index_role >= 0:
            self.combo_role.setCurrentIndex(index_role)

        session.close()

        self.label_mode_form.setText(f"Modifier « {user.username} »")
        self.bouton_valider.setText("Enregistrer les modifications")
        self.bouton_annuler.show()

    def _reinitialiser_formulaire(self):
        self.user_en_edition_id = None
        self.champ_username.clear()
        self.champ_nom_complet.clear()
        self.champ_email.clear()
        self.champ_mdp.clear()
        self.case_actif.setChecked(True)
        self.label_mode_form.setText("Ajouter un utilisateur")
        self.bouton_valider.setText("+ Ajouter l'utilisateur")
        self.bouton_annuler.hide()

    def _valider_formulaire(self):
        if self.user_en_edition_id is None:
            self._ajouter_utilisateur()
        else:
            self._modifier_utilisateur()

    def _ajouter_utilisateur(self):
        username = self.champ_username.text().strip()
        mdp = self.champ_mdp.text()

        if not username or not mdp:
            QMessageBox.warning(self, "Champs manquants", "Le nom d'utilisateur et le mot de passe sont obligatoires à la création.")
            return

        session = SessionLocal()
        if session.query(User).filter_by(username=username).first():
            session.close()
            QMessageBox.warning(self, "Nom déjà utilisé", f"Le nom d'utilisateur '{username}' existe déjà.")
            return

        nouvel_utilisateur = User(
            username=username,
            password_hash=bcrypt.hashpw(mdp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            nom_complet=self.champ_nom_complet.text().strip() or None,
            email=self.champ_email.text().strip() or None,
            role_id=self.combo_role.currentData(),
            actif=self.case_actif.isChecked()
        )
        session.add(nouvel_utilisateur)
        session.commit()
        session.close()

        self._reinitialiser_formulaire()
        self._charger_utilisateurs()

    def _modifier_utilisateur(self):
        username = self.champ_username.text().strip()

        if not username:
            QMessageBox.warning(self, "Champ manquant", "Le nom d'utilisateur est obligatoire.")
            return

        session = SessionLocal()

        doublon = session.query(User).filter(
            User.username == username, User.id != self.user_en_edition_id
        ).first()
        if doublon:
            session.close()
            QMessageBox.warning(self, "Nom déjà utilisé", f"Le nom d'utilisateur '{username}' est déjà pris.")
            return

        user = session.query(User).filter_by(id=self.user_en_edition_id).first()

        # Protection : empêcher de désactiver le dernier administrateur actif
        if user.actif and not self.case_actif.isChecked():
            role_admin = session.query(Role).filter_by(nom="Administrateur").first()
            if role_admin and user.role_id == role_admin.id:
                nb_admins_actifs = session.query(User).filter_by(role_id=role_admin.id, actif=True).count()
                if nb_admins_actifs <= 1:
                    session.close()
                    QMessageBox.warning(self, "Action refusée", "Impossible de désactiver le dernier administrateur actif.")
                    return

        user.username = username
        user.nom_complet = self.champ_nom_complet.text().strip() or None
        user.email = self.champ_email.text().strip() or None
        user.role_id = self.combo_role.currentData()
        user.actif = self.case_actif.isChecked()

        nouveau_mdp = self.champ_mdp.text()
        if nouveau_mdp:
            user.password_hash = bcrypt.hashpw(nouveau_mdp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        session.commit()
        session.close()

        self._reinitialiser_formulaire()
        self._charger_utilisateurs()

    def _reinitialiser_mot_de_passe(self):
        ligne = self._ligne_selectionnee()
        if ligne is None:
            return

        user_id = int(self.tableau.item(ligne, 0).text())
        username = self.tableau.item(ligne, 1).text()

        nouveau_mdp = "ormvag2026"  # mot de passe temporaire par défaut

        confirmation = QMessageBox.question(
            self, "Réinitialiser le mot de passe",
            f"Réinitialiser le mot de passe de « {username} » à « {nouveau_mdp} » ?\nL'utilisateur devra le changer à sa prochaine connexion.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirmation != QMessageBox.Yes:
            return

        session = SessionLocal()
        user = session.query(User).filter_by(id=user_id).first()
        user.password_hash = bcrypt.hashpw(nouveau_mdp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        session.commit()
        session.close()

        QMessageBox.information(self, "Mot de passe réinitialisé", f"Nouveau mot de passe temporaire : {nouveau_mdp}")