from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QComboBox, QCheckBox, QScrollArea, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QApplication, QTabWidget
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
import os
from datetime import datetime, time, timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure
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

        style_champ = (
            f"QDateEdit {{ color: {COULEURS['texte']}; background-color: white; "
            f"border: 1px solid #ccc; border-radius: 6px; padding: 6px; }}"
        )
        # Choix valable pour tous les types de rapport (Synthèse/Détaillé/Relevé
        # journalier) : soit une période (Du/au), soit un jour unique - jamais les
        # deux en même temps, d'où les radios plutôt que deux champs indépendants.
        self.groupe_mode_date = QButtonGroup(self)
        self.radio_mode_periode = QRadioButton("Période :")
        self.radio_mode_jour = QRadioButton("Jour unique :")
        self.radio_mode_periode.setChecked(True)
        for radio in [self.radio_mode_periode, self.radio_mode_jour]:
            radio.setStyleSheet(self._style_radio())
            self.groupe_mode_date.addButton(radio)
            radio.toggled.connect(self._basculer_mode_date)
            radio.toggled.connect(self._mettre_a_jour_apercu)

        ligne_dates = QHBoxLayout()
        ligne_dates.addWidget(self.radio_mode_periode)

        label_du = QLabel("Du :")
        label_du.setStyleSheet("color: black;")
        ligne_dates.addWidget(label_du)
        self.date_debut = QDateEdit(calendarPopup=True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        self.date_debut.setDate(QDate.currentDate().addMonths(-1))
        self.date_debut.setMinimumWidth(110)
        self.date_debut.setStyleSheet(style_champ)
        self._appliquer_style_calendrier(self.date_debut)
        self.date_debut.dateChanged.connect(self._mettre_a_jour_apercu)
        ligne_dates.addWidget(self.date_debut)

        label_au = QLabel("au :")
        label_au.setStyleSheet("color: black;")
        ligne_dates.addWidget(label_au)
        self.date_fin = QDateEdit(calendarPopup=True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setMinimumWidth(110)
        self.date_fin.setStyleSheet(style_champ)
        self._appliquer_style_calendrier(self.date_fin)
        self.date_fin.dateChanged.connect(self._mettre_a_jour_apercu)
        ligne_dates.addWidget(self.date_fin)

        ligne_dates.addStretch()
        layout_droit.addLayout(ligne_dates)

        ligne_jour = QHBoxLayout()
        ligne_jour.addWidget(self.radio_mode_jour)
        self.date_jour = QDateEdit(calendarPopup=True)
        self.date_jour.setDisplayFormat("dd/MM/yyyy")
        self.date_jour.setDate(QDate.currentDate())
        self.date_jour.setMinimumWidth(110)
        self.date_jour.setStyleSheet(style_champ)
        self._appliquer_style_calendrier(self.date_jour)
        self.date_jour.dateChanged.connect(self._mettre_a_jour_apercu)
        self.date_jour.setEnabled(False)
        ligne_jour.addWidget(self.date_jour)
        ligne_jour.addStretch()
        layout_droit.addLayout(ligne_jour)

        # Raccourcis de période
        ligne_raccourcis = QHBoxLayout()
        for texte, jours in [("7 derniers jours", 7), ("15 derniers jours", 15), ("Ce mois-ci", 30)]:
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
            radio.toggled.connect(self._mettre_a_jour_apercu)
        # Charge l'aperçu automatiquement dès la sélection de ce type (pas besoin
        # du bouton pour le premier chargement) - un changement de date ensuite
        # nécessite en revanche un clic explicite, pour ne pas relancer une
        # requête réseau à chaque frappe (voir _mettre_a_jour_apercu).
        self.radio_journalier.toggled.connect(
            lambda coche: self._apercu_journalier() if coche else None)
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

        self.label_apercu = QLabel("")
        self.label_apercu.setWordWrap(True)
        self.label_apercu.setStyleSheet(f"color: {COULEURS['texte']}; font-size: 12px;")
        layout_droit.addWidget(self.label_apercu)

        # Aperçu des données brutes (Synthèse/Détaillé uniquement - le relevé
        # journalier n'agrège pas de lignes Mesure individuelles, voir
        # _mettre_a_jour_apercu). Limité a quelques lignes : un simple aperçu,
        # pas un remplacement du rapport complet.
        self.table_apercu = QTableWidget()
        self.table_apercu.setColumnCount(5)
        self.table_apercu.setHorizontalHeaderLabels(
            ["Station", "Date", "Type", "Pluie (mm)", "Temp. moy (°C)"])
        self.table_apercu.verticalHeader().setVisible(False)
        self.table_apercu.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_apercu.setSelectionMode(QAbstractItemView.NoSelection)
        self.table_apercu.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_apercu.setMaximumHeight(220)
        self.table_apercu.setStyleSheet(f"""
            QTableWidget {{ background-color: white; color: {COULEURS['texte']}; border: 1px solid #e0e4e8; gridline-color: #ecf0f1; }}
            QTableWidget::item:alternate {{ background-color: #fafbfc; }}
            QHeaderView::section {{ background-color: #ecf0f1; color: {COULEURS['texte']}; padding: 4px; border: none; font-weight: bold; font-size: 11px; }}
        """)
        self.table_apercu.setAlternatingRowColors(True)
        layout_droit.addWidget(self.table_apercu)

        # Le relevé journalier interroge le site source en direct par station
        # (voir generateur_rapport._pluie_24h) : contrairement au reste de
        # l'aperçu, non recalculé a chaque frappe mais seulement sur demande.
        self.bouton_apercu_journalier = QPushButton("Actualiser l'aperçu (interroge le site source)")
        self.bouton_apercu_journalier.setCursor(Qt.PointingHandCursor)
        self.bouton_apercu_journalier.setStyleSheet("""
            QPushButton { background-color: #ecf0f1; color: #2c3e50; border-radius: 6px; padding: 8px 12px; }
            QPushButton:hover { background-color: #d5dbdb; }
        """)
        self.bouton_apercu_journalier.setVisible(False)
        self.bouton_apercu_journalier.clicked.connect(self._apercu_journalier)
        layout_droit.addWidget(self.bouton_apercu_journalier)

        # Un onglet par jour en mode "période" (chaque jour a ses propres valeurs,
        # un seul tableau ne suffirait pas) - masqué en mode "jour unique", qui
        # réutilise table_apercu directement.
        self.tabs_apercu_journalier = QTabWidget()
        self.tabs_apercu_journalier.setMaximumHeight(220)
        self.tabs_apercu_journalier.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid #e0e4e8; }}
            QTabBar::tab {{ background-color: #ecf0f1; color: {COULEURS['texte']}; padding: 6px 12px; }}
            QTabBar::tab:selected {{ background-color: {COULEURS['primaire']}; color: white; }}
        """)
        self.tabs_apercu_journalier.setVisible(False)
        layout_droit.addWidget(self.tabs_apercu_journalier)

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

    def _style_calendrier(self):
        return """
            QCalendarWidget { background-color: white; min-width: 320px; min-height: 240px; }
            QCalendarWidget QToolButton { color: #2c3e50; background-color: white; font-weight: bold; }
            QCalendarWidget QMenu { background-color: white; color: #2c3e50; }
            QCalendarWidget QSpinBox { color: #2c3e50; background-color: white; }
            QCalendarWidget QAbstractItemView { background-color: white; color: #2c3e50; selection-background-color: rgba(215, 215, 215, 255); selection-color: #2c3e50; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: rgba(215, 215, 215, 255); }
            QCalendarWidget QHeaderView::section { background-color: rgba(215, 215, 215, 255); color: #2c3e50; padding: 4px; font-weight: bold; border: none; }
        """

    def _appliquer_style_calendrier(self, champ_date):
        """Applique le style clair au calendrier d'un QDateEdit. En-tête des jours en
        gris avec texte foncé plutôt que fond bleu marine avec texte blanc : sur
        certains postes (thème sombre Windows), le blanc forcé par CSS restait
        illisible (repris par la palette système) - le texte foncé, lui, s'affiche
        correctement quel que soit le thème."""
        calendrier = champ_date.calendarWidget()
        calendrier.setStyleSheet(self._style_calendrier())

    def _charger_stations(self):
        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).order_by(Station.nom).all()
        session.close()

        for station in stations:
            case = QCheckBox(f"{station.code} - {station.nom}")
            case.setStyleSheet("color: #2c3e50;")
            case.setChecked(False)
            case.setEnabled(False)  # désactivée tant que "Toutes les stations" est cochée
            case.stateChanged.connect(self._mettre_a_jour_apercu)
            self.layout_cases.addWidget(case)
            self.cases_stations[station.id] = case

        self.layout_cases.addStretch()
        self._mettre_a_jour_apercu()

    def _basculer_toutes_stations(self):
        actif = not self.case_toutes.isChecked()
        for case in self.cases_stations.values():
            case.setEnabled(actif)
        self._mettre_a_jour_apercu()

    NB_LIGNES_APERCU = 8

    def _mettre_a_jour_apercu(self):
        """Résumé + aperçu des données qui seraient incluses, mis à jour à chaque
        changement de filtre - pas de requête réseau ici (voir _pluie_24h) : pour
        le relevé journalier, on affiche juste le cycle visé plutôt que d'interroger
        le site source à chaque frappe, beaucoup trop lent pour un simple aperçu ;
        ce relevé agrège de toute façon des cumuls, pas des lignes Mesure brutes,
        donc le mini-tableau ne s'y applique pas."""
        if self.radio_journalier.isChecked():
            self.table_apercu.setVisible(False)
            self.tabs_apercu_journalier.setVisible(False)
            self.bouton_apercu_journalier.setVisible(True)
            if self.radio_mode_jour.isChecked():
                jour = self.date_jour.date().toPython()
                periode_txt = f"cycle 6h-6h se terminant le {jour.strftime('%d/%m/%Y')}"
            else:
                debut = self.date_debut.date().toPython()
                fin = self.date_fin.date().toPython()
                nb_jours = (fin - debut).days + 1
                periode_txt = (
                    f"{nb_jours} relevé(s) distinct(s), un par jour du "
                    f"{debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
                )
            self.label_apercu.setText(
                f"Aperçu : relevé officiel SED (Excel), toutes les stations actives, {periode_txt}."
            )
            return

        self.bouton_apercu_journalier.setVisible(False)
        self.tabs_apercu_journalier.setVisible(False)
        self.table_apercu.setVisible(True)
        self.table_apercu.setHorizontalHeaderLabels(
            ["Station", "Date", "Type", "Pluie (mm)", "Temp. moy (°C)"])
        station_ids = self._stations_selectionnees()
        date_debut, date_fin = self._bornes_periode()
        nb_stations = len(self.cases_stations) if station_ids is None else len(station_ids)

        session = SessionLocal()
        try:
            base = session.query(Mesure).filter(
                Mesure.date_heure >= date_debut, Mesure.date_heure <= date_fin,
            )
            if station_ids:
                base = base.filter(Mesure.station_id.in_(station_ids))
            nb_mesures = base.count()
            premieres_lignes = base.order_by(Mesure.date_heure.desc()).limit(self.NB_LIGNES_APERCU).all()

            self.table_apercu.setRowCount(len(premieres_lignes))
            for row, m in enumerate(premieres_lignes):
                valeurs = [
                    m.station.nom,
                    m.date_heure.strftime("%d/%m/%Y"),
                    m.type_donnee or "—",
                    f"{m.pluie:.1f}" if m.pluie is not None else "—",
                    f"{m.temperature:.1f}" if m.temperature is not None else "—",
                ]
                for col, valeur in enumerate(valeurs):
                    item = QTableWidgetItem(valeur)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table_apercu.setItem(row, col, item)
        finally:
            session.close()

        self.label_apercu.setText(
            f"Aperçu : {nb_stations} station(s) sélectionnée(s) · période du "
            f"{date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')} · "
            f"{nb_mesures} mesure(s) trouvée(s)"
            + (f", {self.NB_LIGNES_APERCU} plus récentes ci-dessous :" if nb_mesures else "."))

    def _appliquer_raccourci(self, jours):
        self.radio_mode_periode.setChecked(True)
        self.date_debut.setDate(QDate.currentDate().addDays(-jours))
        self.date_fin.setDate(QDate.currentDate())

    def _basculer_mode_date(self):
        """Période et Jour unique s'excluent mutuellement, quel que soit le type de
        rapport choisi : jamais les deux jeux de champs actifs en même temps."""
        est_jour = self.radio_mode_jour.isChecked()
        self.date_debut.setEnabled(not est_jour)
        self.date_fin.setEnabled(not est_jour)
        self.date_jour.setEnabled(est_jour)

    def _basculer_type_rapport(self):
        """Le relevé journalier ne concerne que toutes les stations actives et n'existe
        qu'au format Excel (voir generateur_rapport.generer_excel_releve_precipitations) :
        les contrôles qui ne s'appliquent pas à ce type sont désactivés plutôt que
        masqués, pour que leur absence d'effet reste visible."""
        est_journalier = self.radio_journalier.isChecked()

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

    def _bornes_periode(self):
        """(date_debut, date_fin) selon le mode actif : soit la période Du/au, soit
        un jour unique traité comme une période d'un seul jour."""
        if self.radio_mode_jour.isChecked():
            jour = self.date_jour.date().toPython()
            return (datetime.combine(jour, datetime.min.time()), datetime.combine(jour, datetime.max.time()))
        return (
            datetime.combine(self.date_debut.date().toPython(), datetime.min.time()),
            datetime.combine(self.date_fin.date().toPython(), datetime.max.time()),
        )

    def _generer(self):
        if self.radio_journalier.isChecked():
            self._generer_journalier()
            return

        station_ids = self._stations_selectionnees()
        date_debut, date_fin = self._bornes_periode()

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

    def _lignes_releve(self, df):
        """Construit les lignes du relevé : une par station, puis une moyenne par
        province, puis la moyenne ORMVAG globale - pour situer chaque station par
        rapport à son secteur et au réseau complet. Retourne une liste de
        (est_moyenne, valeurs) ; est_moyenne sert à distinguer visuellement les
        lignes de synthèse des lignes de station."""
        colonnes = ["Pluie 24h (mm)", "Pluie 15 derniers jours (mm)",
                    "Pluie campagne n (mm)", "Pluie campagne n-1 (mm)"]
        lignes = []
        for _, station_ligne in df.iterrows():
            lignes.append((False, [station_ligne["Station"]] + [f"{station_ligne[c]:.1f}" for c in colonnes]))

        if "Province" in df.columns:
            for province in sorted(df["Province"].dropna().unique()):
                sous_ensemble = df[df["Province"] == province]
                lignes.append((True, [f"Moyenne {province}"] + [f"{sous_ensemble[c].mean():.1f}" for c in colonnes]))

        lignes.append((True, ["Moyenne ORMVAG"] + [f"{df[c].mean():.1f}" for c in colonnes]))
        return lignes

    def _peupler_table_releve(self, table, df):
        """Remplit un QTableWidget déjà créé avec les lignes du relevé - factorisé
        car utilisé aussi bien pour le jour unique (table persistante) que pour
        chaque onglet du mode période (table créée à la volée)."""
        lignes = self._lignes_releve(df)
        table.setRowCount(len(lignes))
        for row, (est_moyenne, valeurs) in enumerate(lignes):
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(str(valeur))
                item.setTextAlignment(Qt.AlignCenter)
                if est_moyenne:
                    police = item.font()
                    police.setBold(True)
                    item.setFont(police)
                    item.setBackground(QColor("#eaf2f8"))
                table.setItem(row, col, item)

    def _construire_table_releve(self, df):
        """Construit un QTableWidget peuplé des colonnes du relevé - factorisé car
        utilisé aussi bien pour le jour unique que pour chaque onglet du mode
        période."""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Station", "Pluie 24h (mm)", "Pluie 15j (mm)",
            "Pluie campagne n (mm)", "Pluie campagne n-1 (mm)",
        ])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(f"""
            QTableWidget {{ background-color: white; color: {COULEURS['texte']}; border: none; gridline-color: #ecf0f1; }}
            QTableWidget::item:alternate {{ background-color: #fafbfc; }}
            QHeaderView::section {{ background-color: #ecf0f1; color: {COULEURS['texte']}; padding: 4px; border: none; font-weight: bold; font-size: 11px; }}
        """)
        self._peupler_table_releve(table, df)
        return table

    def _apercu_journalier(self):
        """Aperçu du relevé officiel avec les vraies valeurs (Pluie 24h précise,
        voir generateur_rapport._pluie_24h) : interroge le site source pour les
        14 stations (× le nombre de jours en mode période), donc assez lent -
        confirmation demandée avant de lancer, que le déclenchement soit
        automatique (sélection du type) ou manuel (bouton actualiser)."""
        mode_jour_unique = self.radio_mode_jour.isChecked()
        if mode_jour_unique:
            message = "Charger l'aperçu interroge le site source pour les 14 stations : ça prend quelques secondes."
        else:
            nb_jours = (self.date_fin.date().toPython() - self.date_debut.date().toPython()).days + 1
            message = (
                f"Charger l'aperçu interroge le site source pour les 14 stations, "
                f"{nb_jours} fois (un par jour de la période) : ça peut prendre plusieurs minutes."
            )
        reponse = QMessageBox.question(
            self, "Charger l'aperçu ?", f"{message}\nContinuer ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reponse != QMessageBox.Yes:
            return

        if mode_jour_unique:
            self._apercu_journalier_jour_unique()
        else:
            self._apercu_journalier_periode()

    def _apercu_journalier_jour_unique(self):
        jour = self.date_jour.date().toPython()
        date_fin_cycle = datetime.combine(jour, time(6, 0))

        self.bouton_apercu_journalier.setEnabled(False)
        self.label_statut.setText("Chargement de l'aperçu (interrogation du site source)...")
        QApplication.processEvents()
        try:
            df, infos, _ = recuperer_releve_precipitations(date_fin=date_fin_cycle)
            if df.empty:
                QMessageBox.information(self, "Aucune donnée", "Aucune mesure trouvée pour ce cycle.")
                return

            self.tabs_apercu_journalier.setVisible(False)
            self.table_apercu.setVisible(True)
            self.table_apercu.setHorizontalHeaderLabels([
                "Station", "Pluie 24h (mm)", "Pluie 15j (mm)",
                "Pluie campagne n (mm)", "Pluie campagne n-1 (mm)",
            ])
            self._peupler_table_releve(self.table_apercu, df)
            self.label_statut.setText(
                f"Aperçu du cycle se terminant le {jour.strftime('%d/%m/%Y')} "
                f"(campagne {infos['libelle_campagne']})."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger l'aperçu :\n{e}")
            self.label_statut.setText("")
        finally:
            self.bouton_apercu_journalier.setEnabled(True)

    def _apercu_journalier_periode(self):
        jour_debut = self.date_debut.date().toPython()
        jour_fin = self.date_fin.date().toPython()
        if not self._confirmer_periode_journaliere(jour_debut, jour_fin, "prévisualiser"):
            return

        self.bouton_apercu_journalier.setEnabled(False)
        self.table_apercu.setVisible(False)
        self.tabs_apercu_journalier.clear()
        erreurs = []
        jour = jour_debut
        while jour <= jour_fin:
            self.label_statut.setText(
                f"Chargement de l'aperçu du {jour.strftime('%d/%m/%Y')} "
                f"(interrogation du site source)..."
            )
            QApplication.processEvents()
            try:
                df, _, _ = recuperer_releve_precipitations(
                    date_fin=datetime.combine(jour, time(6, 0)))
                if not df.empty:
                    onglet = self._construire_table_releve(df)
                    self.tabs_apercu_journalier.addTab(onglet, jour.strftime("%d/%m"))
            except Exception as e:
                erreurs.append(f"{jour.strftime('%d/%m/%Y')} : {e}")
            jour += timedelta(days=1)

        self.tabs_apercu_journalier.setVisible(self.tabs_apercu_journalier.count() > 0)
        message = f"Aperçu généré pour {self.tabs_apercu_journalier.count()} jour(s)."
        if erreurs:
            message += " Erreurs : " + "; ".join(erreurs)
        self.label_statut.setText(message)
        self.bouton_apercu_journalier.setEnabled(True)

    def _generer_journalier(self):
        if self.radio_mode_periode.isChecked():
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
        if self.radio_mode_periode.isChecked():
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
        date_debut, date_fin = self._bornes_periode()
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