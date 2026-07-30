import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QAbstractItemView
)
from PySide6.QtCore import Qt, QUrl, QTimer
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
from app.services.generateur_rapport import lire_cache_releve_reseau


VARIABLES = {
    "Pluie (mm)": "pluie",
    "Température (°C)": "temperature",
    "Évapotranspiration (mm)": "eto",
    "Humidité (%)": "humidite",
    "Vent (km/h)": "vent",
    "Rayonnement (W/m²)": "rayonnement",
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
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")

        # Références conservées pour permettre un rafraîchissement sans
        # reconstruire toute l'interface (évite de recréer QWebEngineView etc.)
        self._valeurs_releve_reseau = {}
        self._alertes_frames = {}

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

        layout.addSpacing(10)

        # --- Relevé des précipitations (moyenne réseau) ---
        self.bloc_releve_reseau = self._creer_bloc_releve_reseau()
        layout.addWidget(self.bloc_releve_reseau)

        # --- Corps : graphique (gauche) + résumé réseau et carte (droite) ---
        corps = QHBoxLayout()
        corps.setSpacing(24)

        corps.addWidget(self._bloc_graphique(), stretch=3)
        corps.addWidget(self._diviseur_vertical())

        colonne_droite = QVBoxLayout()
        colonne_droite.setSpacing(18)
        colonne_droite.addWidget(self._creer_bloc_stats_reseau())
        colonne_droite.addWidget(self._bloc_carte_miniature(), stretch=1)
        corps.addLayout(colonne_droite, stretch=2)

        layout.addLayout(corps)

        # Premier chargement des données dynamiques
        self.rafraichir()

    def rafraichir_donnees(self):
        """Point d'entrée utilisé par l'event_bus (ex: après l'import de 6h)."""
        self.rafraichir()

    def _demarrer_actualisation_auto(self):
        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self.rafraichir)
        self._minuteur.start(INTERVALLE_RAFRAICHISSEMENT_MS)

    def resizeEvent(self, event):
        """Sans ça, le graphique matplotlib garde la mise en page calculée lors du
        premier tracé et ne remplit pas le panneau une fois la fenêtre agrandie
        (grand vide sous le graphique) — on relayoute/redessine sans requêter la
        base de nouveau."""
        super().resizeEvent(event)
        if hasattr(self, "canvas") and self.figure.axes:
            self.figure.tight_layout()
            self.canvas.draw()

    # ============== RAFRAÎCHISSEMENT GLOBAL ==============

    def rafraichir(self):
        """Recharge toutes les données et met à jour les widgets existants
        (sans reconstruire toute l'interface)."""
        maintenant = datetime.now()
        self.label_sous_titre.setText(f"Aperçu général — {self._date_francaise(maintenant)}")
        self.label_derniere_maj.setText(f"Dernière mise à jour : {maintenant.strftime('%H:%M:%S')}")

        derniers_indicateurs = self._recuperer_derniers_indicateurs()

        self._mettre_a_jour_bandeau_alertes(derniers_indicateurs)
        self._mettre_a_jour_tableau_stats()
        self._mettre_a_jour_releve_reseau()
        self._tracer_graphique()
        self._mettre_a_jour_carte_miniature()

    @staticmethod
    def _date_francaise(dt: datetime) -> str:
        jour = JOURS_FR[dt.weekday()]
        mois = MOIS_FR[dt.month - 1]
        return f"{jour} {dt.day:02d} {mois} {dt.year}"

    # ============== BANDE DE STATISTIQUES ==============

    def _creer_carte(self, cle, titre, couleur, dict_cible):
        """Crée un bloc de statistique (typographie + liséré de couleur, pas de
        carte-boîte avec ombre) et conserve les références des labels dynamiques
        (valeur + tendance) dans dict_cible[cle] pour mise à jour ultérieure."""
        conteneur = QWidget()
        conteneur.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(conteneur)
        layout.setContentsMargins(20, 0, 20, 4)
        layout.setSpacing(8)

        liseré = QFrame()
        liseré.setFixedHeight(3)
        liseré.setStyleSheet(f"background-color: {couleur}; border: none;")
        layout.addWidget(liseré)

        layout.addSpacing(6)

        ligne_valeur = QHBoxLayout()
        ligne_valeur.setSpacing(8)
        label_valeur = QLabel("—")
        label_valeur.setStyleSheet(
            f"font-size: 30px; font-weight: 700; color: {COULEURS['texte']}; "
            f"border: none; background: transparent;"
        )
        ligne_valeur.addWidget(label_valeur)

        label_tendance = QLabel("")
        label_tendance.setStyleSheet("font-size: 12px; font-weight: bold; border: none; background: transparent;")
        ligne_valeur.addWidget(label_tendance)
        ligne_valeur.addStretch()
        layout.addLayout(ligne_valeur)

        label_titre = QLabel(titre.upper())
        label_titre.setWordWrap(True)
        label_titre.setStyleSheet(
            f"color: {COULEURS['neutre']}; font-size: 11.5px; font-weight: 700; "
            f"letter-spacing: 0.5px; border: none; background: transparent;"
        )
        layout.addWidget(label_titre)
        layout.addStretch()

        dict_cible[cle] = {"valeur": label_valeur, "tendance": label_tendance}
        return conteneur

    def _diviseur_vertical(self):
        diviseur = QFrame()
        diviseur.setFixedWidth(1)
        diviseur.setStyleSheet("background-color: #e3e7eb; border: none;")
        return diviseur

    def _creer_bloc_stats_reseau(self):
        bloc = QWidget()
        bloc.setStyleSheet("background: transparent;")
        bloc.setMaximumHeight(160)
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bloc_titre, _ = self._titre_section("Résumé du réseau")
        layout.addLayout(bloc_titre)

        self.table_stats_reseau = QTableWidget()
        self.table_stats_reseau.setColumnCount(2)
        self.table_stats_reseau.setRowCount(4)
        self.table_stats_reseau.horizontalHeader().setVisible(False)
        self.table_stats_reseau.verticalHeader().setVisible(False)
        self.table_stats_reseau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_stats_reseau.setSelectionMode(QAbstractItemView.NoSelection)
        self.table_stats_reseau.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_stats_reseau.setShowGrid(False)
        self.table_stats_reseau.setFixedHeight(120)
        self.table_stats_reseau.setStyleSheet(f"""
            QTableWidget {{ background-color: white; color: {COULEURS['texte']}; border: none; }}
            QTableWidget::item {{ border-bottom: 1px solid #ecf0f1; }}
        """)

        libelles = ["Stations actives", "Mesures aujourd'hui", "Température moyenne", "Surveillance"]
        for row, libelle in enumerate(libelles):
            item_libelle = QTableWidgetItem(libelle)
            item_libelle.setForeground(QColor(COULEURS["neutre"]))
            self.table_stats_reseau.setItem(row, 0, item_libelle)
        layout.addWidget(self.table_stats_reseau)

        return bloc

    def _mettre_a_jour_tableau_stats(self):
        nb_stations = self._compter_stations_actives()
        nb_mesures_aujourdhui, temp_moyenne, delta_temp = self._stats_mesures_aujourdhui()

        valeur_temp = f"{temp_moyenne} °C" if temp_moyenne is not None else "—"
        if delta_temp is not None and abs(delta_temp) >= 0.05:
            fleche = "▲" if delta_temp > 0 else "▼"
            valeur_temp += f"  {fleche}{abs(delta_temp):.1f}"

        valeurs = [
            str(nb_stations),
            str(nb_mesures_aujourdhui),
            valeur_temp,
            "Complète" if nb_mesures_aujourdhui == 14 else "Non complète" if nb_mesures_aujourdhui > 0 else "En attente",
        ]
        for row, valeur in enumerate(valeurs):
            item = QTableWidgetItem(valeur)
            item.setForeground(QColor(COULEURS["texte"]))
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.table_stats_reseau.setItem(row, 1, item)

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
        nb_inondation = sum(1 for i in indicateurs if i.risque_inondation)
        nb_stress = sum(1 for i in indicateurs if i.stress_thermique)
        nb_deficit = sum(1 for i in indicateurs if (i.bilan_hydrique_7j or 0) < 0)

        valeurs = {
            "inondation": ("Risque d'inondation", nb_inondation, COULEURS["violet"]),
            "stress": ("Stress thermique", nb_stress, COULEURS["attention"]),
            "deficit": ("Déficit hydrique (7j)", nb_deficit, COULEURS["danger"]),
        }

        if not self._alertes_frames:
            for i, (cle, (titre, nombre, couleur)) in enumerate(valeurs.items()):
                if i > 0:
                    self.layout_alertes.addWidget(self._diviseur_vertical())
                liseré, label = self._creer_carte_alerte(titre, couleur)
                self._alertes_frames[cle] = {"liseré": liseré, "label": label, "titre": titre, "couleur": couleur}

        for cle, (titre, nombre, couleur) in valeurs.items():
            refs = self._alertes_frames[cle]
            actif = nombre > 0
            couleur_active = couleur if actif else "#d5dbdb"
            couleur_texte = couleur if actif else COULEURS["neutre"]
            refs["liseré"].setStyleSheet(f"background-color: {couleur_active}; border: none;")
            refs["label"].setText(f"{nombre} — {titre}")
            refs["label"].setStyleSheet(
                f"color: {couleur_texte}; font-weight: {700 if actif else 500}; font-size: 13px; "
                f"border: none; background: transparent;"
            )

    def _creer_carte_alerte(self, titre, couleur):
        conteneur = QWidget()
        conteneur.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(conteneur)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(6)

        liseré = QFrame()
        liseré.setFixedHeight(3)
        layout.addWidget(liseré)

        label = QLabel()
        layout.addWidget(label)

        self.layout_alertes.addWidget(conteneur, stretch=1)
        return liseré, label

    # ============== GRAPHIQUE ENRICHI ==============

    def _titre_section(self, texte, taille=13.5):
        """Titre de section flanqué d'une règle inférieure — remplace la
        carte-boîte blanche avec ombre par une structure typographique."""
        bloc_titre = QVBoxLayout()
        bloc_titre.setSpacing(8)
        label = QLabel(texte)
        label.setStyleSheet(f"font-weight: 700; color: {COULEURS['texte']}; font-size: {taille}px; border: none;")
        bloc_titre.addWidget(label)
        regle = QFrame()
        regle.setFixedHeight(2)
        regle.setStyleSheet(f"background-color: {COULEURS['primaire']}; border: none;")
        bloc_titre.addWidget(regle)
        return bloc_titre, label

    def _bloc_graphique(self):
        bloc = QWidget()
        bloc.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        bloc_titre, _ = self._titre_section("Tendance — 7 derniers jours (moyenne toutes stations)")
        layout.addLayout(bloc_titre)

        entete = QHBoxLayout()
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
        # Pas de plafond de hauteur : le graphique remplit l'espace vertical
        # disponible du panneau (auparavant limité à 190px, laissant un grand
        # vide sous le graphique alors que la colonne de droite est plus haute).
        self.canvas.setMinimumHeight(260)
        layout.addWidget(self.canvas, stretch=1)

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
            # fill_between remplit jusqu'à 0 par défaut, ce qui forçait l'axe Y à
            # démarrer à 0 lors de l'auto-échelle et écrasait la variation réelle
            # de la courbe. On borne explicitement l'axe autour des données.
            marge = (max(valeurs) - min(valeurs)) * 0.15 or 1
            ax.set_ylim(min(valeurs) - marge, max(valeurs) + marge)
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

    # ============== MINI-TABLEAU RELEVÉ RÉSEAU (moyenne ORMVAG) ==============

    def _creer_bloc_releve_reseau(self):
        bloc = QWidget()
        bloc.setStyleSheet("background: transparent;")
        bloc.setMaximumHeight(190)
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bloc_titre, _ = self._titre_section("Relevé des précipitations — moyenne ORMVAG", taille=15)
        layout.addLayout(bloc_titre)

        self.label_releve_indisponible = QLabel(
            "Pas encore disponible — se met à jour lors de la première tâche quotidienne (8h)."
        )
        self.label_releve_indisponible.setWordWrap(True)
        self.label_releve_indisponible.setStyleSheet(
            f"color: {COULEURS['texte']}; font-size: 12px; border: none; background: transparent;"
        )
        layout.addWidget(self.label_releve_indisponible)

        self.widget_grille_releve_reseau = QWidget()
        self.widget_grille_releve_reseau.setStyleSheet("background: transparent;")
        grille_releve_reseau = QHBoxLayout(self.widget_grille_releve_reseau)
        grille_releve_reseau.setContentsMargins(0, 0, 0, 0)
        grille_releve_reseau.setSpacing(0)

        cartes_releve = [
            ("pluie_24h", "Pluie 24h (mm)", COULEURS["info"]),
            ("pluie_15j", "Pluie 15 derniers jours (mm)", COULEURS["primaire"]),
            ("campagne_n", "Pluie campagne (n) (mm)", COULEURS["succes"]),
            ("campagne_n1", "Pluie campagne (n-1) (mm)", COULEURS["neutre"]),
        ]
        for i, (cle, titre_carte, couleur) in enumerate(cartes_releve):
            if i > 0:
                grille_releve_reseau.addWidget(self._diviseur_vertical())
            grille_releve_reseau.addWidget(
                self._creer_carte(cle, titre_carte, couleur, self._valeurs_releve_reseau), stretch=1
            )
        layout.addWidget(self.widget_grille_releve_reseau)

        return bloc

    def _mettre_a_jour_releve_reseau(self):
        cache = lire_cache_releve_reseau()
        if cache is None:
            self.label_releve_indisponible.setVisible(True)
            self.widget_grille_releve_reseau.setVisible(False)
            return

        self.label_releve_indisponible.setVisible(False)
        self.widget_grille_releve_reseau.setVisible(True)

        correspondance = {
            "pluie_24h": "Pluie 24h (mm)",
            "pluie_15j": "Pluie 15 derniers jours (mm)",
            "campagne_n": "Pluie campagne n (mm)",
            "campagne_n1": "Pluie campagne n-1 (mm)",
        }
        for cle, cle_cache in correspondance.items():
            self._valeurs_releve_reseau[cle]["valeur"].setText(f"{cache.get(cle_cache, 0):.1f}")

    # ============== CARTE MINIATURE ==============

    def _bloc_carte_miniature(self):
        bloc = QWidget()
        bloc.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(bloc)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bloc_titre, _ = self._titre_section("Statut des stations")
        layout.addLayout(bloc_titre)

        legende = QHBoxLayout()
        for couleur, texte in [
            (COULEURS["succes"], "OK"), (COULEURS["attention"], "Déficit"), (COULEURS["danger"], "innondation / stress")
        ]:
            point = QLabel("●")
            point.setStyleSheet(f"color: {couleur}; font-size: 12px; border: none; background: transparent;")
            legende.addWidget(point)
            texte_label = QLabel(texte)
            texte_label.setStyleSheet(
                f"color: {COULEURS['neutre']}; font-size: 11px; border: none; background: transparent;"
            )
            legende.addWidget(texte_label)
            legende.addSpacing(8)
        legende.addStretch()
        layout.addLayout(legende)

        self.vue_web = QWebEngineView()
        # Hauteur minimale plutôt que fixe : la carte remplit l'espace restant
        # de la colonne de droite au lieu de laisser un grand vide sous elle.
        self.vue_web.setMinimumHeight(200)
        layout.addWidget(self.vue_web, stretch=1)

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
                if ind.risque_inondation or ind.stress_thermique:
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