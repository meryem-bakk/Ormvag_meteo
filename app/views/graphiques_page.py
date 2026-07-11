from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame,
    QCheckBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QTimeEdit
)
from PySide6.QtCore import Qt, QDate, QTime, QTimer
from PySide6.QtGui import QColor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from datetime import datetime
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


VARIABLES = {
    "Température (°C)": "temperature",
    "Humidité (%)": "humidite",
    "Pluie (mm)": "pluie",
    "Vent (km/h)": "vent",
    "Rayonnement (W/m²)": "rayonnement",
    "Évapotranspiration (mm)": "eto",
}

COULEURS_STATIONS = ["#1a5276", "#c0392b", "#27ae60", "#e67e22", "#8e44ad", "#16a085", "#d35400"]


class GraphiquesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.cases_stations = {}
        self._build_ui()
        self._charger_stations()
        self._tracer_graphique()
        self._demarrer_actualisation_auto()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        entete = QHBoxLayout()
        titre = QLabel("Graphiques")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        entete.addWidget(titre)
        entete.addStretch()

        self.label_derniere_maj = QLabel("")
        self.label_derniere_maj.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        entete.addWidget(self.label_derniere_maj)

        bouton_actualiser = QPushButton("🔄 Actualiser")
        bouton_actualiser.setCursor(Qt.PointingHandCursor)
        bouton_actualiser.setStyleSheet("""
            QPushButton { background-color: white; color: #1a5276; border: 1px solid #d5dbdb; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #eaf2f8; }
        """)
        bouton_actualiser.clicked.connect(self.rafraichir)
        entete.addWidget(bouton_actualiser)

        layout.addLayout(entete)

        # --- Contrôles : variable + période ---
        controles = QFrame()
        controles.setStyleSheet("QFrame { background-color: white; border-radius: 8px; padding: 12px; }")
        layout_controles = QHBoxLayout(controles)
        layout_controles.setSpacing(10)

        layout_controles.addWidget(QLabel("Variable :"))
        self.combo_variable = QComboBox()
        self.combo_variable.addItems(VARIABLES.keys())
        self.combo_variable.currentIndexChanged.connect(self._tracer_graphique)
        layout_controles.addWidget(self.combo_variable)

        layout_controles.addWidget(QLabel("Du :"))
        self.date_debut = QDateEdit(calendarPopup=True)
        self.date_debut.setDisplayFormat("dd/MM/yyyy")
        self.date_debut.setDate(QDate.currentDate().addDays(-7))
        self.date_debut.setFixedWidth(120)
        self.date_debut.setStyleSheet(self._style_champ())
        layout_controles.addWidget(self.date_debut)

        self.heure_debut = QTimeEdit()
        self.heure_debut.setDisplayFormat("HH:mm")
        self.heure_debut.setTime(QTime(0, 0))
        self.heure_debut.setFixedWidth(90)
        self.heure_debut.setStyleSheet(self._style_champ())
        layout_controles.addWidget(self.heure_debut)

        layout_controles.addWidget(QLabel("au :"))
        self.date_fin = QDateEdit(calendarPopup=True)
        self.date_fin.setDisplayFormat("dd/MM/yyyy")
        self.date_fin.setDate(QDate.currentDate())
        self.date_fin.setFixedWidth(120)
        self.date_fin.setStyleSheet(self._style_champ())
        layout_controles.addWidget(self.date_fin)

        self.heure_fin = QTimeEdit()
        self.heure_fin.setDisplayFormat("HH:mm")
        self.heure_fin.setTime(QTime(23, 59))
        self.heure_fin.setFixedWidth(90)
        self.heure_fin.setStyleSheet(self._style_champ())
        layout_controles.addWidget(self.heure_fin)

        self.date_debut.dateChanged.connect(self._tracer_graphique)
        self.date_fin.dateChanged.connect(self._tracer_graphique)
        self.heure_debut.timeChanged.connect(self._tracer_graphique)
        self.heure_fin.timeChanged.connect(self._tracer_graphique)

        layout_controles.addStretch()

        self.bouton_refresh = QPushButton("🔄 Rafraîchir les stations")
        self.bouton_refresh.clicked.connect(self.actualiser_stations)
        layout_controles.addWidget(self.bouton_refresh)
        
        layout.addWidget(controles)

        # --- Corps : cases à cocher (gauche) + graphique (droite) ---
        corps = QHBoxLayout()
        corps.setSpacing(16)

        # Colonne gauche : sélection des stations à comparer
        panneau_stations = QFrame()
        panneau_stations.setFixedWidth(220)
        panneau_stations.setStyleSheet("QFrame { background-color: white; border-radius: 8px; padding: 12px; }")
        layout_panneau = QVBoxLayout(panneau_stations)

        label_comparer = QLabel("Comparer :")
        label_comparer.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout_panneau.addWidget(label_comparer)

        zone_defilement = QScrollArea()
        zone_defilement.setWidgetResizable(True)
        zone_defilement.setStyleSheet("QScrollArea { border: none; background-color: white; }")
        conteneur_cases = QWidget()
        conteneur_cases.setStyleSheet("background-color: white;")
        self.layout_cases = QVBoxLayout(conteneur_cases)
        zone_defilement.setWidget(conteneur_cases)
        layout_panneau.addWidget(zone_defilement)

        corps.addWidget(panneau_stations)

        # Colonne droite : graphique + tableau de synthèse
        colonne_droite = QVBoxLayout()

        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)
        colonne_droite.addWidget(self.canvas, stretch=2)

        label_synthese = QLabel("Tableau de synthèse")
        label_synthese.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 8px;")
        colonne_droite.addWidget(label_synthese)

        self.tableau_synthese = QTableWidget()
        self.tableau_synthese.setColumnCount(6)
        self.tableau_synthese.setHorizontalHeaderLabels(["Station", "Moyenne", "Min", "Max", "Écart-type", "Nb mesures"])
        self.tableau_synthese.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableau_synthese.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau_synthese.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 8px; color: #2c3e50; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 6px; border: none; font-weight: bold; }
        """)
        colonne_droite.addWidget(self.tableau_synthese, stretch=1)

        corps.addLayout(colonne_droite, stretch=1)
        layout.addLayout(corps)
    
    def rafraichir(self):
        self._tracer_graphique()
        from datetime import datetime
        self.label_derniere_maj.setText(f"Mis à jour : {datetime.now().strftime('%H:%M:%S')}")

    def _demarrer_actualisation_auto(self):
        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self.rafraichir)
        self._minuteur.start(5 * 60 * 1000)

    def rafraichir_donnees(self):
        self.rafraichir()

    def _style_champ(self):
        return """
            QDateEdit, QTimeEdit { color: #2c3e50; background-color: white; border: 1px solid #ccc; border-radius: 6px; padding: 6px; }
        """

    def _charger_stations(self, codes_a_precocher=None):

        if codes_a_precocher is None:
            codes_a_precocher = set()
        session = SessionLocal()
        stations = (
            session.query(Station)
            .filter_by(actif=True)
            .order_by(Station.nom)
            .all()
        )
        session.close()
        for i, station in enumerate(stations):
            case = QCheckBox(f"{station.code} - {station.nom}")
            if station.code in codes_a_precocher:
                case.setChecked(True)
            else:
                case.setChecked(i < 3)
            case.stateChanged.connect(self._tracer_graphique)
            self.layout_cases.addWidget(case)
            self.cases_stations[station.id] = (case, station)
        self.layout_cases.addStretch()

    def actualiser_stations(self):
        codes_coches = {
            station.code
            for _, (case, station) in self.cases_stations.items()
            if case.isChecked()
        }
        while self.layout_cases.count():
            item = self.layout_cases.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.cases_stations = {}

        self._charger_stations(codes_coches)
        self._tracer_graphique()

    def _stations_cochees(self):
        return [(sid, station) for sid, (case, station) in self.cases_stations.items() if case.isChecked()]

    def _tracer_graphique(self):
        stations_cochees = self._stations_cochees()
        nom_variable = self.combo_variable.currentText()
        colonne = VARIABLES.get(nom_variable, "temperature")

        debut = datetime.combine(self.date_debut.date().toPython(), self.heure_debut.time().toPython())
        fin = datetime.combine(self.date_fin.date().toPython(), self.heure_fin.time().toPython())

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        session = SessionLocal()
        lignes_synthese = []

        for i, (station_id, station) in enumerate(stations_cochees):
            mesures = session.query(Mesure).filter(
                Mesure.station_id == station_id,
                Mesure.date_heure >= debut,
                Mesure.date_heure <= fin
            ).order_by(Mesure.date_heure).all()

            if not mesures:
                continue

            dates = [m.date_heure for m in mesures]
            valeurs = [getattr(m, colonne) for m in mesures]
            couleur = COULEURS_STATIONS[i % len(COULEURS_STATIONS)]

            ax.plot(dates, valeurs, label=station.code, color=couleur, linewidth=1.5)

            moyenne = sum(valeurs) / len(valeurs)
            variance = sum((v - moyenne) ** 2 for v in valeurs) / len(valeurs)
            ecart_type = variance ** 0.5

            lignes_synthese.append((station.code, moyenne, min(valeurs), max(valeurs), ecart_type, len(valeurs)))

        session.close()

        if stations_cochees and lignes_synthese:
            ax.legend(fontsize=8, loc="upper right")
        ax.set_title(f"{nom_variable} — comparaison entre stations", fontsize=11, color="#2c3e50")
        ax.tick_params(axis='x', rotation=30, labelsize=8)
        ax.tick_params(axis='y', labelsize=8)
        ax.grid(True, alpha=0.2)
        self.figure.tight_layout()
        self.canvas.draw()

        self._remplir_synthese(lignes_synthese)

    def _remplir_synthese(self, lignes):
        self.tableau_synthese.setRowCount(len(lignes))
        for i, (code, moyenne, mini, maxi, ecart_type, nb) in enumerate(lignes):
            valeurs = [code, f"{moyenne:.1f}", f"{mini:.1f}", f"{maxi:.1f}", f"{ecart_type:.2f}", str(nb)]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                item.setForeground(QColor("#2c3e50"))
                # Align numeric values to the right, keep station name left-aligned
                if col == 0:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tableau_synthese.setItem(i, col, item)