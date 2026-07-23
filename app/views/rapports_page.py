from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QComboBox, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, QDate
import os
from datetime import datetime, time, timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.services.generateur_rapport import (
    recuperer_donnees, generer_pdf, generer_excel, generer_csv,
    recuperer_synthese, generer_graphique_temperature, generer_pdf_synthese,
    generer_excel_synthese, generer_csv_synthese,
    recuperer_releve_precipitations, generer_excel_releve_precipitations,
)
from app.services.email_service import envoyer_rapport_par_email
from app.utils.theme import COULEURS, titre_section, diviseur_vertical
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.platypus import Image
from app.models.indicateur_journalier import IndicateurJournalier

class RapportsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")
        self.cases_stations = {}
        self._build_ui()
        self._charger_stations()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        titre = QLabel("Rapports")
        titre.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COULEURS['texte']};")
        layout.addWidget(titre)

        corps = QHBoxLayout()
        corps.setSpacing(24)

        # --- Colonne gauche : stations ---
        panneau_stations = QWidget()
        panneau_stations.setFixedWidth(310)
        panneau_stations.setStyleSheet("background: transparent;")
        layout_panneau = QVBoxLayout(panneau_stations)
        layout_panneau.setContentsMargins(0, 0, 0, 0)
        layout_panneau.setSpacing(10)

        bloc_titre_stations, _ = titre_section("Stations")
        layout_panneau.addLayout(bloc_titre_stations)

        self.case_toutes = QCheckBox("Toutes les stations")
        self.case_toutes.setChecked(True)
        self.case_toutes.setStyleSheet(f"color: {COULEURS['texte']}; font-weight: bold; margin-bottom: 6px;")
        self.case_toutes.stateChanged.connect(self._basculer_toutes_stations)
        layout_panneau.addWidget(self.case_toutes)

        zone_defilement = QScrollArea()
        zone_defilement.setWidgetResizable(True)
        zone_defilement.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        conteneur = QWidget()
        conteneur.setStyleSheet("background: transparent;")
        self.layout_cases = QVBoxLayout(conteneur)
        zone_defilement.setWidget(conteneur)
        layout_panneau.addWidget(zone_defilement)

        corps.addWidget(panneau_stations)
        corps.addWidget(diviseur_vertical())

        # --- Colonne droite : paramètres du rapport ---
        panneau_droit = QWidget()
        panneau_droit.setStyleSheet("background: transparent;")
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setContentsMargins(0, 0, 0, 0)
        layout_droit.setSpacing(14)

        label_periode = QLabel("Période")
        label_periode.setStyleSheet(f"font-weight: bold; color: {COULEURS['texte']};")
        layout_droit.addWidget(label_periode)

        ligne_dates = QHBoxLayout()
        style_champ = (
            f"QDateEdit {{ color: {COULEURS['texte']}; background-color: white; "
            f"border: 1px solid #ccc; border-radius: 6px; padding: 6px; }}"
        )

        ligne_dates.addWidget(QLabel("Du :"))
        self.date_debut = QDateEdit(calendarPopup=True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        self.date_debut.setDate(QDate.currentDate().addMonths(-1))
        self.date_debut.setMinimumWidth(110)
        self.date_debut.setStyleSheet(style_champ)
        ligne_dates.addWidget(self.date_debut)

        ligne_dates.addWidget(QLabel("au :"))
        self.date_fin = QDateEdit(calendarPopup=True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setMinimumWidth(110)
        self.date_fin.setStyleSheet(style_champ)
        ligne_dates.addWidget(self.date_fin)

        ligne_dates.addStretch()
        layout_droit.addLayout(ligne_dates)

        # Utilisé uniquement par le type "Relevé journalier" ci-dessous : soit un seul
        # cycle 6h-6h (jour unique), soit un relevé distinct pour chaque jour de la
        # période déjà définie ci-dessus (même principe que le rattrapage automatique
        # du scheduler après une absence prolongée — voir scheduler._envoyer_rapport_pour_jour).
        ligne_mode_journalier = QHBoxLayout()
        self.groupe_mode_journalier = QButtonGroup(self)
        self.radio_jour_unique = QRadioButton("Jour unique :")
        self.radio_jour_periode = QRadioButton("Un relevé par jour de la période ci-dessus")
        self.radio_jour_unique.setChecked(True)
        for radio in [self.radio_jour_unique, self.radio_jour_periode]:
            radio.setStyleSheet(self._style_radio())
            radio.setEnabled(False)
            self.groupe_mode_journalier.addButton(radio)
            ligne_mode_journalier.addWidget(radio)
            radio.toggled.connect(self._basculer_type_rapport)

        self.date_jour = QDateEdit(calendarPopup=True)
        self.date_jour.setDisplayFormat("dd/MM/yyyy")
        self.date_jour.setDate(QDate.currentDate())
        self.date_jour.setMinimumWidth(110)
        self.date_jour.setStyleSheet(style_champ)
        self.date_jour.setEnabled(False)
        ligne_mode_journalier.addWidget(self.date_jour)
        ligne_mode_journalier.addStretch()
        layout_droit.addLayout(ligne_mode_journalier)

        # Raccourcis de période
        ligne_raccourcis = QHBoxLayout()
        for texte, jours in [("7 derniers jours", 7), ("30 derniers jours", 30), ("Ce mois-ci", 30)]:
            bouton = QPushButton(texte)
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.setStyleSheet("""
                QPushButton { background-color: #ecf0f1; color: #2c3e50; border-radius: 6px; padding: 6px 12px; }
                QPushButton:hover { background-color: #d5dbdb; }
            """)
            bouton.clicked.connect(lambda checked=False, j=jours: self._appliquer_raccourci(j))
            ligne_raccourcis.addWidget(bouton)
        ligne_raccourcis.addStretch()
        layout_droit.addLayout(ligne_raccourcis)

        label_type = QLabel("Type de rapport")
        label_type.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 10px;")
        layout_droit.addWidget(label_type)

        ligne_type = QHBoxLayout()
        self.groupe_type = QButtonGroup(self)

        self.radio_synthese = QRadioButton("Synthèse (indicateurs + graphique)")
        self.radio_detaille = QRadioButton("Détaillé (données brutes jour par jour)")
        self.radio_journalier = QRadioButton("Relevé journalier (précipitations, format SED)")
        self.radio_synthese.setChecked(True)

        for radio in [self.radio_synthese, self.radio_detaille, self.radio_journalier]:
            radio.setStyleSheet(self._style_radio())
            self.groupe_type.addButton(radio)
            ligne_type.addWidget(radio)
            radio.toggled.connect(self._basculer_type_rapport)
        ligne_type.addStretch()
        layout_droit.addLayout(ligne_type)

        label_format = QLabel("Format de sortie")
        label_format.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 10px;")
        layout_droit.addWidget(label_format)

        ligne_format = QHBoxLayout()
        self.groupe_format = QButtonGroup(self)

        self.radio_pdf = QRadioButton("PDF")
        self.radio_excel = QRadioButton("Excel")
        self.radio_csv = QRadioButton("CSV")
        self.radio_pdf.setChecked(True)

        for radio in [self.radio_pdf, self.radio_excel, self.radio_csv]:
            radio.setStyleSheet(self._style_radio())
            self.groupe_format.addButton(radio)
            ligne_format.addWidget(radio)
        ligne_format.addStretch()
        layout_droit.addLayout(ligne_format)

        layout_droit.addStretch()

        self.label_statut = QLabel("")
        self.label_statut.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout_droit.addWidget(self.label_statut)

        ligne_boutons = QHBoxLayout()
        ligne_boutons.setSpacing(10)

        bouton_generer = QPushButton("Générer le rapport")
        bouton_generer.setCursor(Qt.PointingHandCursor)
        bouton_generer.setMinimumHeight(42)
        bouton_generer.setStyleSheet("""
            QPushButton { background-color: #1a5276; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #154360; }
        """)
        bouton_generer.clicked.connect(self._generer)
        ligne_boutons.addWidget(bouton_generer, stretch=1)

        bouton_email = QPushButton("Envoyer par email")
        bouton_email.setCursor(Qt.PointingHandCursor)
        bouton_email.setMinimumHeight(42)
        bouton_email.setStyleSheet("""
            QPushButton { background-color: #229954; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #1e8449; }
        """)
        bouton_email.clicked.connect(self._envoyer_par_email)
        ligne_boutons.addWidget(bouton_email, stretch=1)

        layout_droit.addLayout(ligne_boutons)

        corps.addWidget(panneau_droit, stretch=1)
        layout.addLayout(corps)

    def _style_radio(self):
        """Distingue clairement l'option cochée (rond bleu plein) des autres
        (rond gris vide) — sans ça, Qt rend par défaut tous les ronds identiques."""
        return f"""
            QRadioButton {{ color: {COULEURS['texte']}; spacing: 6px; }}
            QRadioButton::indicator {{
                width: 15px; height: 15px; border-radius: 8px;
                border: 2px solid #c7ced4; background: white;
            }}
            QRadioButton::indicator:hover {{ border: 2px solid {COULEURS['primaire']}; }}
            QRadioButton::indicator:checked {{
                border: 2px solid {COULEURS['primaire']}; background: {COULEURS['primaire']};
            }}
        """

    def _charger_stations(self):
        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).order_by(Station.nom).all()
        session.close()

        for station in stations:
            case = QCheckBox(f"{station.code} - {station.nom}")
            case.setStyleSheet("color: #2c3e50;")
            case.setChecked(False)
            case.setEnabled(False)  # désactivée tant que "Toutes les stations" est cochée
            self.layout_cases.addWidget(case)
            self.cases_stations[station.id] = case

        self.layout_cases.addStretch()

    def _basculer_toutes_stations(self):
        actif = not self.case_toutes.isChecked()
        for case in self.cases_stations.values():
            case.setEnabled(actif)

    def _appliquer_raccourci(self, jours):
        self.date_debut.setDate(QDate.currentDate().addDays(-jours))
        self.date_fin.setDate(QDate.currentDate())

    def _basculer_type_rapport(self):
        """Le relevé journalier porte sur un cycle 6h-6h (jour unique ou un relevé par
        jour d'une période), toutes stations actives confondues, et n'existe qu'au
        format Excel (voir generateur_rapport.generer_excel_releve_precipitations) :
        les contrôles qui ne s'appliquent pas à ce type sont désactivés plutôt que
        masqués, pour que leur absence d'effet reste visible."""
        est_journalier = self.radio_journalier.isChecked()
        est_jour_unique = est_journalier and self.radio_jour_unique.isChecked()
        est_journalier_periode = est_journalier and self.radio_jour_periode.isChecked()

        self.radio_jour_unique.setEnabled(est_journalier)
        self.radio_jour_periode.setEnabled(est_journalier)
        self.date_jour.setEnabled(est_jour_unique)
        self.date_debut.setEnabled((not est_journalier) or est_journalier_periode)
        self.date_fin.setEnabled((not est_journalier) or est_journalier_periode)

        self.case_toutes.setEnabled(not est_journalier)
        for case in self.cases_stations.values():
            case.setEnabled((not est_journalier) and (not self.case_toutes.isChecked()))

        self.radio_pdf.setEnabled(not est_journalier)
        self.radio_csv.setEnabled(not est_journalier)
        if est_journalier:
            self.radio_excel.setChecked(True)

    def _stations_selectionnees(self):
        if self.case_toutes.isChecked():
            return None  # None = toutes
        return [sid for sid, case in self.cases_stations.items() if case.isChecked()]

    def _generer(self):
        if self.radio_journalier.isChecked():
            self._generer_journalier()
            return

        station_ids = self._stations_selectionnees()
        date_debut = datetime.combine(self.date_debut.date().toPython(), datetime.min.time())
        date_fin = datetime.combine(self.date_fin.date().toPython(), datetime.max.time())

        if self.radio_pdf.isChecked():
            filtre, extension = "Fichier PDF (*.pdf)", ".pdf"
        elif self.radio_excel.isChecked():
            filtre, extension = "Fichier Excel (*.xlsx)", ".xlsx"
        else:
            filtre, extension = "Fichier CSV (*.csv)", ".csv"

        type_rapport = "synthese" if self.radio_synthese.isChecked() else "detaille"
        nom_defaut = f"rapport_ormvag_{type_rapport}_{date_debut.strftime('%Y%m%d')}_{date_fin.strftime('%Y%m%d')}{extension}"
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", nom_defaut, filtre)
        if not chemin:
            return

        self.label_statut.setText("Génération du rapport...")

        try:
            if self.radio_synthese.isChecked():
                df = recuperer_synthese(station_ids, date_debut, date_fin)
                if df.empty:
                    QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour cette sélection.")
                    self.label_statut.setText("")
                    return

                if self.radio_pdf.isChecked():
                    graphique = generer_graphique_temperature(station_ids, date_debut, date_fin)
                    generer_pdf_synthese(chemin, date_debut, date_fin, df, graphique)
                elif self.radio_excel.isChecked():
                    generer_excel_synthese(chemin, df)
                else:
                    generer_csv_synthese(chemin, df)
            else:
                df = recuperer_donnees(station_ids, date_debut, date_fin)
                if df.empty:
                    QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour cette sélection.")
                    self.label_statut.setText("")
                    return

                if self.radio_pdf.isChecked():
                    titre = "Toutes les stations" if station_ids is None else f"{len(station_ids)} station(s) sélectionnée(s)"
                    generer_pdf(chemin, titre, date_debut, date_fin, df)
                elif self.radio_excel.isChecked():
                    generer_excel(chemin, df)
                else:
                    generer_csv(chemin, df)

            self.label_statut.setText(f"Rapport généré : {chemin}")
            QMessageBox.information(self, "Rapport généré", f"Le rapport a été enregistré :\n{chemin}")
        except Exception as e:
            self.label_statut.setText("")
            QMessageBox.critical(self, "Erreur", f"Impossible de générer le rapport :\n{e}")

    def _generer_journalier(self):
        if self.radio_jour_periode.isChecked():
            self._generer_journalier_periode()
        else:
            self._generer_journalier_jour_unique()

    def _generer_journalier_jour_unique(self):
        date_fin_cycle = datetime.combine(self.date_jour.date().toPython(), time(6, 0))
        nom_defaut = f"rapport_journalier_{date_fin_cycle.strftime('%Y%m%d')}.xlsx"
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le relevé journalier", nom_defaut, "Fichier Excel (*.xlsx)")
        if not chemin:
            return

        self.label_statut.setText("Génération du relevé journalier...")
        try:
            df, infos, tableau_mensuel = recuperer_releve_precipitations(date_fin=date_fin_cycle)
            if df.empty:
                QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour ce jour.")
                self.label_statut.setText("")
                return

            generer_excel_releve_precipitations(chemin, df, infos, tableau_mensuel)
            self.label_statut.setText(f"Relevé généré : {chemin}")
            QMessageBox.information(self, "Rapport généré", f"Le relevé a été enregistré :\n{chemin}")
        except Exception as e:
            self.label_statut.setText("")
            QMessageBox.critical(self, "Erreur", f"Impossible de générer le relevé :\n{e}")

    def _confirmer_periode_journaliere(self, jour_debut, jour_fin, verbe):
        """Un relevé par jour interroge le site source en direct (pluie 24h précise,
        voir generateur_rapport._pluie_24h) : au-delà d'un mois, le nombre d'allers-retours
        réseau (14 stations x N jours) devient long — on prévient avant de lancer."""
        if jour_debut > jour_fin:
            QMessageBox.warning(self, "Période invalide", "La date de début doit précéder la date de fin.")
            return False

        nb_jours = (jour_fin - jour_debut).days + 1
        if nb_jours > 31:
            reponse = QMessageBox.question(
                self, "Période longue",
                f"{nb_jours} jours sélectionnés : chaque jour interroge le site source pour "
                f"les 14 stations, cela peut prendre plusieurs minutes.\nContinuer à {verbe} ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reponse != QMessageBox.Yes:
                return False
        return True

    def _generer_journalier_periode(self):
        jour_debut = self.date_debut.date().toPython()
        jour_fin = self.date_fin.date().toPython()
        if not self._confirmer_periode_journaliere(jour_debut, jour_fin, "générer"):
            return

        dossier = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination")
        if not dossier:
            return

        self.label_statut.setText("Génération des relevés journaliers...")
        nb_generes = 0
        erreurs = []
        jour = jour_debut
        while jour <= jour_fin:
            date_fin_cycle = datetime.combine(jour, time(6, 0))
            try:
                df, infos, tableau_mensuel = recuperer_releve_precipitations(date_fin=date_fin_cycle)
                if not df.empty:
                    chemin = os.path.join(dossier, f"rapport_journalier_{jour.strftime('%Y%m%d')}.xlsx")
                    generer_excel_releve_precipitations(chemin, df, infos, tableau_mensuel)
                    nb_generes += 1
            except Exception as e:
                erreurs.append(f"{jour.strftime('%d/%m/%Y')} : {e}")
            jour += timedelta(days=1)

        message = f"{nb_generes} relevé(s) généré(s) dans :\n{dossier}"
        if erreurs:
            message += "\n\nErreurs :\n" + "\n".join(erreurs)
        self.label_statut.setText(f"{nb_generes} relevé(s) généré(s) dans {dossier}")
        QMessageBox.information(self, "Rapports générés", message)

    def _envoyer_journalier_par_email(self):
        if self.radio_jour_periode.isChecked():
            self._envoyer_journalier_periode_par_email()
        else:
            self._envoyer_journalier_jour_unique_par_email()

    def _envoyer_journalier_jour_unique_par_email(self):
        destinataires = os.getenv("SMTP_DESTINATAIRES", "").strip()
        if not destinataires:
            QMessageBox.warning(
                self, "Configuration manquante",
                "Aucun destinataire configuré.\nRenseignez SMTP_DESTINATAIRES dans le fichier .env."
            )
            return

        date_fin_cycle = datetime.combine(self.date_jour.date().toPython(), time(6, 0))
        reponse = QMessageBox.question(
            self, "Confirmer l'envoi",
            f"Envoyer le relevé journalier du {date_fin_cycle.strftime('%d/%m/%Y')} par email à :\n{destinataires} ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reponse != QMessageBox.Yes:
            return

        os.makedirs("Rapports", exist_ok=True)
        chemin = os.path.join("Rapports", f"rapport_journalier_{date_fin_cycle.strftime('%Y%m%d')}.xlsx")

        self.label_statut.setText("Génération et envoi du relevé journalier...")
        try:
            df, infos, tableau_mensuel = recuperer_releve_precipitations(date_fin=date_fin_cycle)
            if df.empty:
                QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour ce jour.")
                self.label_statut.setText("")
                return

            generer_excel_releve_precipitations(chemin, df, infos, tableau_mensuel)

            envoyer_rapport_par_email(
                chemin,
                sujet=f"ORMVAG — Relevé des précipitations du {date_fin_cycle.strftime('%d/%m/%Y')} "
                      f"(campagne {infos['libelle_campagne']})",
                corps=(
                    "Bonjour,\n\nVeuillez trouver ci-joint le relevé des précipitations du réseau ORMVAG "
                    "(pluie 24h, 15 derniers jours, cumuls de campagne par station et par province).\n\n"
                    "Cordialement,\nORMVAG — Système météo automatisé"
                ),
            )
            self.label_statut.setText(f"Relevé envoyé par email : {chemin}")
            QMessageBox.information(self, "Email envoyé", f"Le relevé a été envoyé par email à :\n{destinataires}")
        except Exception as e:
            self.label_statut.setText("")
            QMessageBox.critical(self, "Erreur", f"Impossible d'envoyer le relevé par email :\n{e}")

    def _envoyer_journalier_periode_par_email(self):
        destinataires = os.getenv("SMTP_DESTINATAIRES", "").strip()
        if not destinataires:
            QMessageBox.warning(
                self, "Configuration manquante",
                "Aucun destinataire configuré.\nRenseignez SMTP_DESTINATAIRES dans le fichier .env."
            )
            return

        jour_debut = self.date_debut.date().toPython()
        jour_fin = self.date_fin.date().toPython()
        if not self._confirmer_periode_journaliere(jour_debut, jour_fin, "envoyer"):
            return

        nb_jours = (jour_fin - jour_debut).days + 1
        reponse = QMessageBox.question(
            self, "Confirmer l'envoi",
            f"Envoyer {nb_jours} relevé(s) journalier(s) distinct(s) (un email par jour) du "
            f"{jour_debut.strftime('%d/%m/%Y')} au {jour_fin.strftime('%d/%m/%Y')} à :\n{destinataires} ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reponse != QMessageBox.Yes:
            return

        os.makedirs("Rapports", exist_ok=True)
        self.label_statut.setText("Génération et envoi des relevés journaliers...")
        nb_envoyes = 0
        erreurs = []
        jour = jour_debut
        while jour <= jour_fin:
            date_fin_cycle = datetime.combine(jour, time(6, 0))
            try:
                df, infos, tableau_mensuel = recuperer_releve_precipitations(date_fin=date_fin_cycle)
                if not df.empty:
                    chemin = os.path.join("Rapports", f"rapport_journalier_{jour.strftime('%Y%m%d')}.xlsx")
                    generer_excel_releve_precipitations(chemin, df, infos, tableau_mensuel)
                    envoyer_rapport_par_email(
                        chemin,
                        sujet=f"ORMVAG — Relevé des précipitations du {jour.strftime('%d/%m/%Y')} "
                              f"(campagne {infos['libelle_campagne']})",
                        corps=(
                            "Bonjour,\n\nVeuillez trouver ci-joint le relevé des précipitations du réseau "
                            "ORMVAG (pluie 24h, 15 derniers jours, cumuls de campagne par station et par "
                            "province).\n\nCordialement,\nORMVAG — Système météo automatisé"
                        ),
                    )
                    nb_envoyes += 1
            except Exception as e:
                erreurs.append(f"{jour.strftime('%d/%m/%Y')} : {e}")
            jour += timedelta(days=1)

        message = f"{nb_envoyes} relevé(s) envoyé(s) par email à :\n{destinataires}"
        if erreurs:
            message += "\n\nErreurs :\n" + "\n".join(erreurs)
        self.label_statut.setText(f"{nb_envoyes} relevé(s) envoyé(s).")
        QMessageBox.information(self, "Emails envoyés", message)

    def _envoyer_par_email(self):
        if self.radio_journalier.isChecked():
            self._envoyer_journalier_par_email()
            return

        destinataires = os.getenv("SMTP_DESTINATAIRES", "").strip()
        if not destinataires:
            QMessageBox.warning(
                self, "Configuration manquante",
                "Aucun destinataire configuré.\nRenseignez SMTP_DESTINATAIRES dans le fichier .env."
            )
            return

        if self.radio_pdf.isChecked():
            extension, nom_format = ".pdf", "PDF"
        elif self.radio_excel.isChecked():
            extension, nom_format = ".xlsx", "Excel"
        else:
            extension, nom_format = ".csv", "CSV"

        reponse = QMessageBox.question(
            self, "Confirmer l'envoi",
            f"Envoyer ce rapport (format {nom_format}) par email à :\n{destinataires} ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reponse != QMessageBox.Yes:
            return

        station_ids = self._stations_selectionnees()
        date_debut = datetime.combine(self.date_debut.date().toPython(), datetime.min.time())
        date_fin = datetime.combine(self.date_fin.date().toPython(), datetime.max.time())
        type_rapport = "synthese" if self.radio_synthese.isChecked() else "detaille"

        os.makedirs("Rapports", exist_ok=True)
        chemin = os.path.join(
            "Rapports",
            f"rapport_ormvag_{type_rapport}_{date_debut.strftime('%Y%m%d')}_{date_fin.strftime('%Y%m%d')}{extension}"
        )

        self.label_statut.setText("Génération et envoi du rapport...")

        try:
            if self.radio_synthese.isChecked():
                df = recuperer_synthese(station_ids, date_debut, date_fin)
                if df.empty:
                    QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour cette sélection.")
                    self.label_statut.setText("")
                    return

                if self.radio_pdf.isChecked():
                    graphique = generer_graphique_temperature(station_ids, date_debut, date_fin)
                    generer_pdf_synthese(chemin, date_debut, date_fin, df, graphique)
                elif self.radio_excel.isChecked():
                    generer_excel_synthese(chemin, df)
                else:
                    generer_csv_synthese(chemin, df)
            else:
                df = recuperer_donnees(station_ids, date_debut, date_fin)
                if df.empty:
                    QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour cette sélection.")
                    self.label_statut.setText("")
                    return

                if self.radio_pdf.isChecked():
                    titre = "Toutes les stations" if station_ids is None else f"{len(station_ids)} station(s) sélectionnée(s)"
                    generer_pdf(chemin, titre, date_debut, date_fin, df)
                elif self.radio_excel.isChecked():
                    generer_excel(chemin, df)
                else:
                    generer_csv(chemin, df)

            envoyer_rapport_par_email(
                chemin,
                sujet=f"ORMVAG — Rapport météo du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                corps=(
                    "Bonjour,\n\nVeuillez trouver ci-joint le rapport météorologique demandé.\n\n"
                    "Cordialement,\nORMVAG — Système météo automatisé"
                ),
            )
            self.label_statut.setText(f"Rapport envoyé par email : {chemin}")
            QMessageBox.information(self, "Email envoyé", f"Le rapport a été envoyé par email à :\n{destinataires}")
        except Exception as e:
            self.label_statut.setText("")
            QMessageBox.critical(self, "Erreur", f"Impossible d'envoyer le rapport par email :\n{e}")