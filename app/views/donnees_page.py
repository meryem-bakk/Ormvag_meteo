from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QFrame, QHeaderView, QDateEdit, QTimeEdit
)
from PySide6.QtCore import Qt, QDate, QTime
from PySide6.QtGui import QColor
from datetime import datetime as dt
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


class DonneesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.mesures_courantes = []
        self._build_ui()
        self._charger_stations_dans_combo()
        self._rechercher()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        titre = QLabel("Données — Mesures")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(titre)

        controles = QFrame()
        controles.setStyleSheet("QFrame { background-color: white; border-radius: 8px; padding: 12px; }")
        layout_controles = QHBoxLayout(controles)
        layout_controles.setSpacing(10)

        layout_controles.addWidget(QLabel("Station :"))
        self.combo_station = QComboBox()
        layout_controles.addWidget(self.combo_station)

        style_calendrier = self._style_calendrier()

        layout_controles.addWidget(QLabel("Du :"))
        self.date_debut = QDateEdit(calendarPopup=True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        self.date_debut.setDate(QDate.currentDate().addDays(-7))
        self.date_debut.setFixedWidth(120)
        self.date_debut.setStyleSheet(self._style_champ_date())
        self.date_debut.calendarWidget().setStyleSheet(style_calendrier)
        layout_controles.addWidget(self.date_debut)

        self.heure_debut = QTimeEdit()
        self.heure_debut.setDisplayFormat("HH:mm")
        self.heure_debut.setTime(QTime(0, 0))
        self.heure_debut.setFixedWidth(90)
        self.heure_debut.setStyleSheet(self._style_champ_date())
        layout_controles.addWidget(self.heure_debut)

        layout_controles.addWidget(QLabel("au :"))
        self.date_fin = QDateEdit(calendarPopup=True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setFixedWidth(120)
        self.date_fin.setStyleSheet(self._style_champ_date())
        self.date_fin.calendarWidget().setStyleSheet(style_calendrier)
        layout_controles.addWidget(self.date_fin)

        self.heure_fin = QTimeEdit()
        self.heure_fin.setDisplayFormat("HH:mm")
        self.heure_fin.setTime(QTime(23, 59))
        self.heure_fin.setFixedWidth(90)
        self.heure_fin.setStyleSheet(self._style_champ_date())
        layout_controles.addWidget(self.heure_fin)

        bouton_rechercher = QPushButton("Rechercher")
        bouton_rechercher.setCursor(Qt.PointingHandCursor)
        bouton_rechercher.setStyleSheet("""
            QPushButton { background-color: #1a5276; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #154360; }
        """)
        bouton_rechercher.clicked.connect(self._rechercher)
        layout_controles.addWidget(bouton_rechercher)

        bouton_exporter = QPushButton("Exporter")
        bouton_exporter.setCursor(Qt.PointingHandCursor)
        bouton_exporter.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #1e8449; }
        """)
        bouton_exporter.clicked.connect(self._exporter_csv)
        layout_controles.addWidget(bouton_exporter)

        layout_controles.addStretch()
        layout.addWidget(controles)

        self.label_resultats = QLabel("")
        self.label_resultats.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self.label_resultats)

        self.tableau = QTableWidget()
        colonnes = [
            "Station", "Date", "Type",
            "ETo (mm)", "Pluie (mm)",
            "Temp. min", "Temp. moy", "Temp. max",
            "Hum. min", "Hum. moy", "Hum. max",
            "Rayonnement", "Vent (km/h)", "Direction"
        ]
        self.tableau.setColumnCount(len(colonnes))
        self.tableau.setHorizontalHeaderLabels(colonnes)

        header = self.tableau.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        largeurs = [70, 90, 80, 70, 70, 75, 75, 75, 75, 75, 75, 95, 90, 80]
        for i, largeur in enumerate(largeurs):
            self.tableau.setColumnWidth(i, largeur)

        self.tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau.setAlternatingRowColors(True)
        self.tableau.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 8px; color: #2c3e50; gridline-color: #ecf0f1; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 6px; border: none; font-weight: bold; }
            QTableWidget::item:selected { background-color: #d6eaf8; color: #1a5276; }
        """)
        layout.addWidget(self.tableau)

    def _style_champ_date(self):
        return """
            QDateEdit, QTimeEdit { color: #2c3e50; background-color: white; border: 1px solid #ccc; border-radius: 6px; padding: 6px; }
        """

    def _style_calendrier(self):
        return """
            QCalendarWidget { background-color: white; min-width: 320px; min-height: 240px; }
            QCalendarWidget QToolButton { color: #2c3e50; background-color: white; font-weight: bold; }
            QCalendarWidget QMenu { background-color: white; color: #2c3e50; }
            QCalendarWidget QSpinBox { color: #2c3e50; background-color: white; }
            QCalendarWidget QAbstractItemView { background-color: white; color: #2c3e50; selection-background-color: #1a5276; selection-color: white; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #ecf0f1; }
            QCalendarWidget QHeaderView::section { background-color: #1a5276; color: white; padding: 4px; font-weight: bold; border: none; }
        """

    def _charger_stations_dans_combo(self):
        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).order_by(Station.nom).all()
        session.close()

        self.combo_station.addItem("Toutes les stations", None)
        for station in stations:
            self.combo_station.addItem(f"{station.code} - {station.nom}", station.id)

    def _rechercher(self):
        station_id = self.combo_station.currentData()
        debut = dt.combine(self.date_debut.date().toPython(), self.heure_debut.time().toPython())
        fin = dt.combine(self.date_fin.date().toPython(), self.heure_fin.time().toPython())

        session = SessionLocal()
        requete = session.query(Mesure).options(joinedload(Mesure.station)).filter(
            Mesure.date_heure >= debut,
            Mesure.date_heure <= fin
        )
        if station_id is not None:
            requete = requete.filter(Mesure.station_id == station_id)

        self.mesures_courantes = requete.order_by(Mesure.date_heure.desc()).limit(500).all()
        session.close()

        self._remplir_tableau()
        self.label_resultats.setText(f"{len(self.mesures_courantes)} mesure(s) affichée(s) (limite : 500)")

    def _remplir_tableau(self):
        self.tableau.setRowCount(len(self.mesures_courantes))
        for i, m in enumerate(self.mesures_courantes):
            valeurs = [
                m.station.code,
                m.date_heure.strftime("%d/%m/%Y"),
                m.type_donnee or "—",
                f"{m.eto:.1f}" if m.eto is not None else "—",
                f"{m.pluie:.1f}" if m.pluie is not None else "—",
                f"{m.temperature_min:.1f}" if m.temperature_min is not None else "—",
                f"{m.temperature:.1f}" if m.temperature is not None else "—",
                f"{m.temperature_max:.1f}" if m.temperature_max is not None else "—",
                f"{m.humidite_min:.1f}" if m.humidite_min is not None else "—",
                f"{m.humidite:.1f}" if m.humidite is not None else "—",
                f"{m.humidite_max:.1f}" if m.humidite_max is not None else "—",
                f"{m.rayonnement:.0f}" if m.rayonnement is not None else "—",
                f"{m.vent:.1f}" if m.vent is not None else "—",
                m.direction_vent or "—",
            ]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                item.setForeground(QColor("#2c3e50"))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tableau.setItem(i, col, item)

    def _exporter_csv(self):
        import csv
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        if not self.mesures_courantes:
            QMessageBox.information(self, "Aucune donnée", "Rien à exporter pour cette recherche.")
            return

        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter en CSV", "mesures.csv", "Fichiers CSV (*.csv)")
        if not chemin:
            return

        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Station", "Date", "Type", "ETo", "Pluie",
                "Temp Min", "Temp Moy", "Temp Max",
                "Hum Min", "Hum Moy", "Hum Max",
                "Rayonnement", "Vent", "Direction Vent"
            ])
            for m in self.mesures_courantes:
                writer.writerow([
                    m.station.code, m.date_heure.strftime("%d/%m/%Y"), m.type_donnee,
                    m.eto, m.pluie, m.temperature_min, m.temperature, m.temperature_max,
                    m.humidite_min, m.humidite, m.humidite_max, m.rayonnement, m.vent, m.direction_vent
                ])

        QMessageBox.information(self, "Export réussi", f"Fichier exporté : {chemin}")