from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDateEdit, QComboBox, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QGraphicsDropShadowEffect, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
import os
from datetime import datetime
from app.database import SessionLocal
from app.models.station import Station
from app.services.generateur_rapport import (
    recuperer_donnees, generer_pdf, generer_excel, generer_csv,
    recuperer_synthese, generer_graphique_temperature, generer_pdf_synthese,
    generer_excel_synthese, generer_csv_synthese,
)
from app.services.email_service import envoyer_rapport_par_email
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.platypus import Image
from app.models.indicateur_journalier import IndicateurJournalier

class RapportsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.cases_stations = {}
        self._build_ui()
        self._charger_stations()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        titre = QLabel("Rapports")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(titre)

        corps = QHBoxLayout()
        corps.setSpacing(16)

        # --- Colonne gauche : stations ---
        panneau_stations = QFrame()
        panneau_stations.setFixedWidth(220)
        panneau_stations.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        panneau_stations.setGraphicsEffect(self._ombre_legere())
        layout_panneau = QVBoxLayout(panneau_stations)
        layout_panneau.setContentsMargins(16, 16, 16, 16)

        label_stations = QLabel("Stations")
        label_stations.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout_panneau.addWidget(label_stations)

        self.case_toutes = QCheckBox("Toutes les stations")
        self.case_toutes.setChecked(True)
        self.case_toutes.setStyleSheet("color: #2c3e50; font-weight: bold; margin-bottom: 6px;")
        self.case_toutes.stateChanged.connect(self._basculer_toutes_stations)
        layout_panneau.addWidget(self.case_toutes)

        zone_defilement = QScrollArea()
        zone_defilement.setWidgetResizable(True)
        zone_defilement.setStyleSheet("QScrollArea { border: none; }")
        conteneur = QWidget()
        self.layout_cases = QVBoxLayout(conteneur)
        zone_defilement.setWidget(conteneur)
        layout_panneau.addWidget(zone_defilement)

        corps.addWidget(panneau_stations)

        # --- Colonne droite : paramètres du rapport ---
        panneau_droit = QFrame()
        panneau_droit.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        panneau_droit.setGraphicsEffect(self._ombre_legere())
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setContentsMargins(20, 20, 20, 20)
        layout_droit.setSpacing(14)

        label_periode = QLabel("Période")
        label_periode.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout_droit.addWidget(label_periode)

        ligne_dates = QHBoxLayout()
        style_champ = "QDateEdit { color: #2c3e50; background-color: white; border: 1px solid #ccc; border-radius: 6px; padding: 6px; }"

        ligne_dates.addWidget(QLabel("Du :"))
        self.date_debut = QDateEdit(calendarPopup=True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        self.date_debut.setDate(QDate.currentDate().addMonths(-1))
        self.date_debut.setStyleSheet(style_champ)
        ligne_dates.addWidget(self.date_debut)

        ligne_dates.addWidget(QLabel("au :"))
        self.date_fin = QDateEdit(calendarPopup=True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setStyleSheet(style_champ)
        ligne_dates.addWidget(self.date_fin)

        ligne_dates.addStretch()
        layout_droit.addLayout(ligne_dates)

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
        self.radio_synthese.setChecked(True)

        for radio in [self.radio_synthese, self.radio_detaille]:
            radio.setStyleSheet("color: #2c3e50;")
            self.groupe_type.addButton(radio)
            ligne_type.addWidget(radio)
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
            radio.setStyleSheet("color: #2c3e50;")
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

        bouton_generer = QPushButton("📄  Générer le rapport")
        bouton_generer.setCursor(Qt.PointingHandCursor)
        bouton_generer.setMinimumHeight(42)
        bouton_generer.setStyleSheet("""
            QPushButton { background-color: #1a5276; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #154360; }
        """)
        bouton_generer.clicked.connect(self._generer)
        ligne_boutons.addWidget(bouton_generer, stretch=1)

        bouton_email = QPushButton("📧  Envoyer par email")
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

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

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

    def _stations_selectionnees(self):
        if self.case_toutes.isChecked():
            return None  # None = toutes
        return [sid for sid, case in self.cases_stations.items() if case.isChecked()]

    def _generer(self):
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

    def _envoyer_par_email(self):
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