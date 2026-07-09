import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QAbstractItemView
)
from PySide6.QtCore import Qt, QUrl, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWebEngineWidgets import QWebEngineView
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from datetime import datetime, timedelta, date
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure
from app.models.indicateur_journalier import IndicateurJournalier

VARIABLES = {
    "Température (°C)": "temperature",
    "Humidité (%)": "humidite",
    "Pluie (mm)": "pluie",
    "Vent (km/h)": "vent",
}

# Noms français pour éviter de dépendre de la locale système (source du bug
# "Thursday 09 july 2026" au lieu de "Jeudi 09 juillet 2026")
JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# Palette centralisée
COULEURS = {
    "primaire": "#1a5276",
    "succes": "#27ae60",
    "attention": "#e67e22",
    "danger": "#c0392b",
    "info": "#3498db",
    "violet": "#8e44ad",
    "neutre": "#7f8c8d",
    "fond": "#f4f6f8",
    "texte": "#2c3e50",
}

# Intervalle d'actualisation automatique (5 minutes)
INTERVALLE_RAFRAICHISSEMENT_MS = 5 * 60 * 1000


def _familles_police_emoji():
    """Retourne une liste de polices capables d'afficher les emojis selon l'OS.
    Corrige l'affichage cassé (icônes manquantes précédées d'une parenthèse)
    observé quand la police par défaut ne gère pas les emojis multi-points."""
    if sys.platform == "win32":
        return ["Segoe UI Emoji", "Segoe UI Symbol"]
    elif sys.platform == "darwin":
        return ["Apple Color Emoji"]
    return ["Noto Color Emoji", "Noto Emoji", "DejaVu Sans"]


def _appliquer_police_emoji(label: QLabel, taille=None):
    police = QFont()
    familles = _familles_police_emoji() + [police.family()]
    police.setFamilies(familles)
    if taille:
        police.setPointSize(taille)
    label.setFont(police)


class DashboardPage(QWidget):
    # Émis quand l'utilisateur double-clique sur une station à risque,
    # pour permettre à la fenêtre principale de naviguer vers cette station.
    station_selectionnee = Signal(int)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")

        # Références conservées pour permettre un rafraîchissement sans
        # reconstruire toute l'interface (évite de recréer QWebEngineView etc.)
        self._valeurs_cartes = {}
        self._alertes_frames = {}
        self._id_station_par_ligne = {}

        self._build_ui()
        self._demarrer_actualisation_auto()

    # ============== CONSTRUCTION INITIALE ==============

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        entete = QHBoxLayout()
        bloc_titres = QVBoxLayout()
        bloc_titres.setSpacing(2)

        titre = QLabel("Tableau de bord")
        titre.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COULEURS['texte']};")
        bloc_titres.addWidget(titre)

        self.label_sous_titre = QLabel()
        self.label_sous_titre.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 12px;")
        bloc_titres.addWidget(self.label_sous_titre)

        entete.addLayout(bloc_titres)
        entete.addStretch()

        self.label_derniere_maj = QLabel()
        self.label_derniere_maj.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 11px;")
        entete.addWidget(self.label_derniere_maj)

        bouton_actualiser = QPushButton("Actualiser")
        _appliquer_police_emoji(bouton_actualiser)
        bouton_actualiser.setText("🔄 Actualiser")
        bouton_actualiser.setCursor(Qt.PointingHandCursor)
        bouton_actualiser.setStyleSheet(f"""
            QPushButton {{
                background-color: white; color: {COULEURS['primaire']};
                border: 1px solid #d5dbdb; border-radius: 6px;
                padding: 6px 14px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #eaf2f8; }}
            QPushButton:pressed {{ background-color: #d4e6f1; }}
        """)
        bouton_actualiser.clicked.connect(self.rafraichir)
        entete.addWidget(bouton_actualiser)

        layout.addLayout(entete)

        # --- Bandeau d'alertes ---
        self.layout_alertes = QHBoxLayout()
        self.layout_alertes.setSpacing(12)
        layout.addLayout(self.layout_alertes)

        # --- Cartes de stats ---
        self.grille_cartes = QGridLayout()
        self.grille_cartes.setSpacing(16)
        layout.addLayout(self.grille_cartes)

        # --- Corps : graphique (gauche) + mini-tableau/carte (droite) ---
        corps = QHBoxLayout()
        corps.setSpacing(16)

        corps.addWidget(self._bloc_graphique(), stretch=1)

        colonne_droite = QVBoxLayout()
        colonne_droite.setSpacing(16)
        self.bloc_risque = self._creer_bloc_stations_a_risque()
        colonne_droite.addWidget(self.bloc_risque)
        colonne_droite.addWidget(self._bloc_carte_miniature())
        corps.addLayout(colonne_droite, stretch=2)

        layout.addLayout(corps)

        # Premier chargement des données dynamiques
        self.rafraichir()

    def _demarrer_actualisation_auto(self):
        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self.rafraichir)
        self._minuteur.start(INTERVALLE_RAFRAICHISSEMENT_MS)

    # ============== RAFRAÎCHISSEMENT GLOBAL ==============

    def rafraichir(self):
        """Recharge toutes les données et met à jour les widgets existants
        (sans reconstruire toute l'interface)."""
        maintenant = datetime.now()
        self.label_sous_titre.setText(f"Aperçu général — {self._date_francaise(maintenant)}")
        self.label_derniere_maj.setText(f"Dernière mise à jour : {maintenant.strftime('%H:%M:%S')}")

        derniers_indicateurs = self._recuperer_derniers_indicateurs()

        self._mettre_a_jour_bandeau_alertes(derniers_indicateurs)
        self._mettre_a_jour_cartes()
        self._mettre_a_jour_stations_a_risque(derniers_indicateurs)
        self._tracer_graphique()
        self._mettre_a_jour_carte_miniature()

    @staticmethod
    def _date_francaise(dt: datetime) -> str:
        jour = JOURS_FR[dt.weekday()]
        mois = MOIS_FR[dt.month - 1]
        return f"{jour} {dt.day:02d} {mois} {dt.year}"

    # ============== UTILITAIRES DE STYLE ==============

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(18)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 28))
        return ombre

    # ============== CARTES DE STATISTIQUES ==============

    def _creer_carte(self, cle, icone, titre, couleur):
        """Crée une carte et conserve les références des labels dynamiques
        (valeur + tendance) dans self._valeurs_cartes[cle] pour mise à jour ultérieure."""
        carte = QFrame()
        carte.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 12px; "
            f"border-left: 4px solid {couleur}; }}"
        )
        carte.setGraphicsEffect(self._ombre_legere())
        carte.setMinimumHeight(104)

        layout = QVBoxLayout(carte)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        ligne_haut = QHBoxLayout()
        label_icone = QLabel(icone)
        _appliquer_police_emoji(label_icone, 16)
        ligne_haut.addWidget(label_icone)
        ligne_haut.addStretch()

        label_tendance = QLabel("")
        label_tendance.setStyleSheet("font-size: 11px; font-weight: bold;")
        ligne_haut.addWidget(label_tendance)
        layout.addLayout(ligne_haut)

        label_valeur = QLabel("—")
        label_valeur.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {couleur};")
        layout.addWidget(label_valeur)

        label_titre = QLabel(titre)
        label_titre.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 12px;")
        layout.addWidget(label_titre)

        self._valeurs_cartes[cle] = {"valeur": label_valeur, "tendance": label_tendance}
        return carte

    def _mettre_a_jour_cartes(self):
        if not self._valeurs_cartes:
            cartes = [
                ("stations", "📡", "Stations actives", COULEURS["primaire"]),
                ("mesures", "📊", "Mesures aujourd'hui", COULEURS["succes"]),
                ("temperature", "🌡", "Température moyenne", COULEURS["attention"]),
                ("surveillance", "🟢", "Surveillance", COULEURS["violet"]),
            ]
            for i, (cle, icone, titre_carte, couleur) in enumerate(cartes):
                self.grille_cartes.addWidget(self._creer_carte(cle, icone, titre_carte, couleur), 0, i)

        nb_stations = self._compter_stations_actives()
        nb_mesures_aujourdhui, temp_moyenne, delta_temp = self._stats_mesures_aujourdhui()

        self._valeurs_cartes["stations"]["valeur"].setText(str(nb_stations))

        self._valeurs_cartes["mesures"]["valeur"].setText(str(nb_mesures_aujourdhui))

        self._valeurs_cartes["temperature"]["valeur"].setText(
            f"{temp_moyenne} °C" if temp_moyenne is not None else "—"
        )
        label_tendance = self._valeurs_cartes["temperature"]["tendance"]
        if delta_temp is None:
            label_tendance.setText("")
        elif abs(delta_temp) < 0.05:
            label_tendance.setText("→ stable")
            label_tendance.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COULEURS['neutre']};")
        else:
            fleche = "▲" if delta_temp > 0 else "▼"
            couleur = COULEURS["danger"] if delta_temp > 0 else COULEURS["info"]
            label_tendance.setText(f"{fleche} {abs(delta_temp):.1f} °C")
            label_tendance.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {couleur};")

        self._valeurs_cartes["surveillance"]["valeur"].setText(
            "Active" if nb_mesures_aujourdhui > 0 else "En attente"
        )

    # ============== DONNÉES ==============

    def _compter_stations_actives(self):
        session = SessionLocal()
        try:
            return session.query(Station).filter_by(actif=True).count()
        finally:
            session.close()

    def _stats_mesures_aujourdhui(self):
        """Retourne (nombre de mesures aujourd'hui, température moyenne du jour,
        écart de température moyenne par rapport à hier)."""
        session = SessionLocal()
        try:
            debut_jour = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            debut_hier = debut_jour - timedelta(days=1)

            nombre = session.query(Mesure).filter(Mesure.date_heure >= debut_jour).count()

            temp_moyenne = session.query(func.avg(Mesure.temperature)).filter(
                Mesure.date_heure >= debut_jour
            ).scalar()

            temp_moyenne_hier = session.query(func.avg(Mesure.temperature)).filter(
                Mesure.date_heure >= debut_hier, Mesure.date_heure < debut_jour
            ).scalar()

            delta = None
            if temp_moyenne is not None and temp_moyenne_hier is not None:
                delta = round(temp_moyenne - temp_moyenne_hier, 1)

            return (
                nombre,
                round(temp_moyenne, 1) if temp_moyenne is not None else None,
                delta,
            )
        finally:
            session.close()

    def _recuperer_derniers_indicateurs(self):
        """Retourne le dernier IndicateurJournalier connu pour chaque station active."""
        session = SessionLocal()
        try:
            sous_requete = session.query(
                IndicateurJournalier.station_id,
                func.max(IndicateurJournalier.date).label("derniere_date")
            ).group_by(IndicateurJournalier.station_id).subquery()

            resultats = session.query(IndicateurJournalier).options(
                joinedload(IndicateurJournalier.station)
            ).join(
                sous_requete,
                (IndicateurJournalier.station_id == sous_requete.c.station_id) &
                (IndicateurJournalier.date == sous_requete.c.derniere_date)
            ).all()

            return resultats
        finally:
            session.close()

    # ============== BANDEAU D'ALERTES ==============

    def _mettre_a_jour_bandeau_alertes(self, indicateurs):
        nb_gel = sum(1 for i in indicateurs if i.gel_detecte)
        nb_stress = sum(1 for i in indicateurs if i.stress_thermique)
        nb_deficit = sum(1 for i in indicateurs if (i.bilan_hydrique_7j or 0) < 0)

        valeurs = {
            "gel": ("❄", "Stations en gel", nb_gel, COULEURS["info"]),
            "stress": ("🌡", "Stress thermique", nb_stress, COULEURS["attention"]),
            "deficit": ("💧", "Déficit hydrique (7j)", nb_deficit, COULEURS["danger"]),
        }

        if not self._alertes_frames:
            for cle, (icone, titre, nombre, couleur) in valeurs.items():
                frame, label = self._creer_carte_alerte(icone, titre, couleur)
                self._alertes_frames[cle] = {"frame": frame, "label": label, "titre": titre, "couleur": couleur}
                self.layout_alertes.addWidget(frame)

        for cle, (icone, titre, nombre, couleur) in valeurs.items():
            refs = self._alertes_frames[cle]
            actif = nombre > 0
            couleur_fond = couleur if actif else "#ecf0f1"
            couleur_texte = "white" if actif else COULEURS["neutre"]
            refs["frame"].setStyleSheet(f"QFrame {{ background-color: {couleur_fond}; border-radius: 8px; }}")
            refs["label"].setText(f"{icone}  {nombre} — {titre}")
            refs["label"].setStyleSheet(f"color: {couleur_texte}; font-weight: bold; font-size: 12px;")

    def _creer_carte_alerte(self, icone, titre, couleur):
        carte = QFrame()
        carte.setMinimumHeight(56)
        layout = QHBoxLayout(carte)
        layout.setContentsMargins(14, 8, 14, 8)

        label = QLabel()
        _appliquer_police_emoji(label)
        layout.addWidget(label)
        layout.addStretch()

        return carte, label

    # ============== GRAPHIQUE ENRICHI ==============

    def _bloc_graphique(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 12px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(16, 16, 16, 16)

        entete = QHBoxLayout()
        label = QLabel("Tendance — 7 derniers jours (moyenne toutes stations)")
        label.setStyleSheet(f"font-weight: bold; color: {COULEURS['texte']}; font-size: 13px;")
        entete.addWidget(label)
        entete.addStretch()

        self.combo_variable = QComboBox()
        self.combo_variable.addItems(VARIABLES.keys())
        self.combo_variable.setCursor(Qt.PointingHandCursor)
        self.combo_variable.setStyleSheet(f"""
            QComboBox {{
                color: {COULEURS['texte']}; background-color: white;
                border: 1px solid #d5dbdb; border-radius: 6px; padding: 4px 8px;
            }}
        """)
        self.combo_variable.currentIndexChanged.connect(self._tracer_graphique)
        entete.addWidget(self.combo_variable)

        layout.addLayout(entete)

        self.figure = Figure(figsize=(5, 2.0))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMaximumHeight(190)
        layout.addWidget(self.canvas)

        return bloc

    def _tracer_graphique(self):
        nom_variable = self.combo_variable.currentText()
        colonne = VARIABLES[nom_variable]

        session = SessionLocal()
        try:
            il_y_a_7_jours = datetime.now() - timedelta(days=7)

            resultats = session.query(
                func.date_trunc('day', Mesure.date_heure).label('jour'),
                func.avg(getattr(Mesure, colonne)).label('valeur_moyenne')
            ).filter(
                Mesure.date_heure >= il_y_a_7_jours
            ).group_by('jour').order_by('jour').all()
        finally:
            session.close()

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if resultats:
            jours = [r.jour for r in resultats]
            valeurs = [r.valeur_moyenne for r in resultats]
            ax.plot(jours, valeurs, color=COULEURS["primaire"], linewidth=1.6, marker="o", markersize=3)
            ax.fill_between(jours, valeurs, color=COULEURS["primaire"], alpha=0.08)
        else:
            ax.text(0.5, 0.5, "Aucune donnée disponible", ha='center', va='center', color=COULEURS["neutre"])

        ax.set_ylabel(nom_variable, fontsize=8)
        ax.tick_params(axis='x', rotation=30, labelsize=7)
        ax.tick_params(axis='y', labelsize=7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2)
        self.figure.tight_layout()
        self.canvas.draw()

    # ============== MINI-TABLEAU STATIONS À RISQUE ==============

    def _creer_bloc_stations_a_risque(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 12px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        bloc.setMaximumHeight(340)
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        label = QLabel("Stations à risque aujourd'hui")
        label.setStyleSheet(f"font-weight: bold; color: {COULEURS['texte']}; font-size: 13px;")
        layout.addWidget(label)

        self.label_risque_vide = QLabel("Aucune alerte active.")
        self.label_risque_vide.setStyleSheet(f"color: {COULEURS['succes']}; font-size: 12px;")
        layout.addWidget(self.label_risque_vide)

        self.table_risque = QTableWidget()
        self.table_risque.setColumnCount(2)
        self.table_risque.setHorizontalHeaderLabels(["Station", "Alerte(s)"])
        self.table_risque.verticalHeader().setVisible(False)
        self.table_risque.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_risque.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_risque.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_risque.setAlternatingRowColors(True)
        self.table_risque.setCursor(Qt.PointingHandCursor)
        self.table_risque.setToolTip("Double-cliquez sur une station pour voir son détail")
        self.table_risque.setStyleSheet(f"""
            QTableWidget {{ background-color: white; color: {COULEURS['texte']}; border: none; gridline-color: #ecf0f1; }}
            QTableWidget::item:alternate {{ background-color: #fafbfc; }}
            QTableWidget::item:selected {{ background-color: #eaf2f8; color: {COULEURS['texte']}; }}
            QHeaderView::section {{ background-color: #ecf0f1; color: {COULEURS['texte']}; padding: 4px; border: none; font-weight: bold; font-size: 11px; }}
        """)
        self.table_risque.cellDoubleClicked.connect(self._on_double_clic_station)
        layout.addWidget(self.table_risque)

        self.label_risque_plus = QLabel("")
        self.label_risque_plus.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 11px;")
        layout.addWidget(self.label_risque_plus)

        return bloc

    def _mettre_a_jour_stations_a_risque(self, indicateurs, limite_affichee=9):
        a_risque = []
        for i in indicateurs:
            alertes = []
            if i.gel_detecte:
                alertes.append("Gel")
            if i.stress_thermique:
                alertes.append("Stress thermique")
            if (i.bilan_hydrique_7j or 0) < 0:
                alertes.append("Déficit hydrique")
            if alertes:
                a_risque.append((i.station_id, i.station.nom, ", ".join(alertes)))

        self._id_station_par_ligne = {}

        if not a_risque:
            self.label_risque_vide.setVisible(True)
            self.table_risque.setVisible(False)
            self.label_risque_plus.setText("")
            return

        self.label_risque_vide.setVisible(False)
        self.table_risque.setVisible(True)

        lignes_affichees = a_risque[:limite_affichee]
        self.table_risque.setRowCount(len(lignes_affichees))
        for row, (station_id, nom, alertes) in enumerate(lignes_affichees):
            item_nom = QTableWidgetItem(nom)
            item_nom.setForeground(QColor(COULEURS["texte"]))
            item_alertes = QTableWidgetItem(alertes)
            item_alertes.setForeground(QColor(COULEURS["danger"]))
            self.table_risque.setItem(row, 0, item_nom)
            self.table_risque.setItem(row, 1, item_alertes)
            self._id_station_par_ligne[row] = station_id

        restant = len(a_risque) - len(lignes_affichees)
        self.label_risque_plus.setText(f"+ {restant} autre(s) station(s) à risque" if restant > 0 else "")

    def _on_double_clic_station(self, row, _colonne):
        station_id = self._id_station_par_ligne.get(row)
        if station_id is not None:
            self.station_selectionnee.emit(station_id)

    # ============== CARTE MINIATURE ==============

    def _bloc_carte_miniature(self):
        bloc = QFrame()
        bloc.setStyleSheet("QFrame { background-color: white; border-radius: 12px; }")
        bloc.setGraphicsEffect(self._ombre_legere())
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(16, 16, 16, 16)

        label = QLabel("Statut des stations")
        label.setStyleSheet(f"font-weight: bold; color: {COULEURS['texte']}; font-size: 13px;")
        layout.addWidget(label)

        legende = QHBoxLayout()
        for couleur, texte in [
            (COULEURS["succes"], "OK"), (COULEURS["attention"], "Déficit"), (COULEURS["danger"], "Gel / stress")
        ]:
            point = QLabel("●")
            point.setStyleSheet(f"color: {couleur}; font-size: 12px;")
            legende.addWidget(point)
            texte_label = QLabel(texte)
            texte_label.setStyleSheet(f"color: {COULEURS['neutre']}; font-size: 11px;")
            legende.addWidget(texte_label)
            legende.addSpacing(8)
        legende.addStretch()
        layout.addLayout(legende)

        self.vue_web = QWebEngineView()
        self.vue_web.setFixedHeight(200)
        layout.addWidget(self.vue_web)

        return bloc

    def _mettre_a_jour_carte_miniature(self):
        html = self._generer_html_carte_miniature()
        self.vue_web.setHtml(html, baseUrl=QUrl("https://ormvag.local/"))

    def _generer_html_carte_miniature(self):
        session = SessionLocal()
        try:
            stations = session.query(Station).filter(
                Station.actif == True,
                Station.latitude != 0,
                Station.longitude != 0
            ).all()

            sous_requete = session.query(
                IndicateurJournalier.station_id,
                func.max(IndicateurJournalier.date).label("derniere_date")
            ).group_by(IndicateurJournalier.station_id).subquery()

            indicateurs = session.query(IndicateurJournalier).join(
                sous_requete,
                (IndicateurJournalier.station_id == sous_requete.c.station_id) &
                (IndicateurJournalier.date == sous_requete.c.derniere_date)
            ).all()
            indicateurs_par_station = {i.station_id: i for i in indicateurs}
        finally:
            session.close()

        if stations:
            centre_lat = sum(s.latitude for s in stations) / len(stations)
            centre_lon = sum(s.longitude for s in stations) / len(stations)
        else:
            centre_lat, centre_lon = 34.26, -6.58

        marqueurs_js = ""
        for s in stations:
            ind = indicateurs_par_station.get(s.id)
            couleur = COULEURS["succes"]
            if ind:
                if ind.gel_detecte or ind.stress_thermique:
                    couleur = COULEURS["danger"]
                elif (ind.bilan_hydrique_7j or 0) < 0:
                    couleur = COULEURS["attention"]

            nom_echappe = s.nom.replace("'", "\\'")
            marqueurs_js += f"""
                L.circleMarker([{s.latitude}, {s.longitude}], {{
                    radius: 6, fillColor: '{couleur}', color: 'white',
                    weight: 1, opacity: 1, fillOpacity: 0.9
                }}).addTo(map).bindPopup('{nom_echappe}');
            """

        return f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>html, body, #carte {{ height: 100%; margin: 0; padding: 0; }}</style>
        </head><body>
        <div id="carte"></div>
        <script>
            var map = L.map('carte', {{zoomControl: false}}).setView([{centre_lat}, {centre_lon}], 8);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap'
            }}).addTo(map);
            {marqueurs_js}
        </script>
        </body></html>
        """