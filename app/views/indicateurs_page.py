from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QFrame, QHeaderView, QGraphicsDropShadowEffect, QGridLayout,
    QAbstractItemView, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from datetime import date, datetime, timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.models.indicateur_journalier import IndicateurJournalier
from app.models.mesure import Mesure
from app.workers.import_worker import IndicateursWorker
from app.services.alertes import detecter_alertes, detecter_anomalies_temperature
from app.services.detection_anomalies_ml import detecter_anomalies_mesures


class IndicateursPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.worker = None
        self._build_ui()
        self._charger_stations_dans_combo()
        self._rafraichir()
        self._demarrer_actualisation_auto()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout_page = QVBoxLayout(self)
        layout_page.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: #f4f6f8; border: none; }")
        layout_page.addWidget(scroll)

        contenu = QWidget()
        contenu.setStyleSheet("background-color: #f4f6f8;")
        scroll.setWidget(contenu)

        layout = QVBoxLayout(contenu)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(20)

        entete = QHBoxLayout()
        titre = QLabel("Indicateurs agroclimatiques")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        entete.addWidget(titre)
        entete.addStretch()

        self.bouton_recalculer = QPushButton("⟳  Recalculer maintenant")
        self.bouton_recalculer.setCursor(Qt.PointingHandCursor)
        self.bouton_recalculer.setStyleSheet(self._style_bouton("#8e44ad", "#6c3483"))
        self.bouton_recalculer.clicked.connect(self._recalculer)
        entete.addWidget(self.bouton_recalculer)

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

        self.bouton_info = QPushButton("ℹ  Définitions et sources des seuils")
        self.bouton_info.setCursor(Qt.PointingHandCursor)
        self.bouton_info.setStyleSheet("""
            QPushButton { background-color: transparent; color: #1a5276; text-align: left; padding: 2px 0; border: none; font-size: 12px; text-decoration: underline; }
            QPushButton:hover { color: #154360; }
        """)
        self.bouton_info.clicked.connect(self._basculer_panneau_info)
        layout.addWidget(self.bouton_info)

        self.panneau_info = QFrame()
        self.panneau_info.setStyleSheet("QFrame { background-color: #fdf6e3; border-radius: 8px; border-left: 4px solid #e67e22; }")
        self.panneau_info.setVisible(False)
        layout_info = QVBoxLayout(self.panneau_info)
        layout_info.setContentsMargins(16, 12, 16, 12)
        layout_info.setSpacing(8)

        definitions = [
            ("Cumul de précipitations (7j/30j)", "Somme des précipitations enregistrées sur les 7 ou 30 derniers jours glissants."),
            ("Bilan hydrique (7j)", "Cumul pluie − cumul ETo sur 7 jours. Positif = excédent d'eau, négatif = déficit (besoin d'irrigation)."),
            ("Jours sans pluie", "Nombre de jours consécutifs sans précipitation enregistrée, jusqu'à la date la plus récente."),
            ("Gel détecté", "Seuil : température minimale < 0°C (définition météorologique standard)."),
            ("Stress thermique", "Seuil : température maximale > 38°C. Seuil indicatif pour cultures méditerranéennes, à ajuster selon les cultures suivies."),
            ("GDD (degrés-jours de croissance)", "Cumulé depuis le 1er septembre (début de saison agricole). Calculé avec une température de base de 10°C, valeur courante pour cultures d'été (maïs) — à ajuster selon la culture."),
            ("Alerte canicule", "Seuil : température maximale > 40°C."),
            ("Alerte vent fort", "Seuil : vitesse du vent > 40 km/h."),
            ("Risque de maladies", "Seuil : humidité relative > 95%. Favorise le développement de maladies fongiques."),
            ("Anomalie capteur (règle)", "Valeur hors plage physiquement plausible, ou écart brutal par rapport aux mesures récentes du même capteur."),
            ("Anomalie détectée par IA", "Modèle Isolation Forest entraîné sur l'historique de toutes les stations : signale les journées dont la combinaison de variables (température, humidité, pluie, vent...) est statistiquement atypique pour la station concernée, même si chaque valeur prise isolément reste plausible."),
        ]

        for titre_def, texte_def in definitions:
            ligne = QLabel(f"<b>{titre_def}</b> — {texte_def}")
            ligne.setStyleSheet("color: #5d4e37; font-size: 12px; border: none; background: transparent;")
            ligne.setWordWrap(True)
            layout_info.addWidget(ligne)

        note_finale = QLabel(
            "Ces seuils sont des valeurs par défaut à visée de prototype. "
            "Ils doivent être validés avec l'ORMVAG selon les cultures réellement suivies dans le périmètre du Gharb."
        )
        note_finale.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic; margin-top: 6px; border: none; background: transparent;")
        note_finale.setWordWrap(True)
        layout_info.addWidget(note_finale)

        layout.addWidget(self.panneau_info)

        self.label_statut = QLabel("")
        self.label_statut.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self.label_statut)

        controles = QFrame()
        controles.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        controles.setGraphicsEffect(self._ombre_legere())
        layout_controles = QHBoxLayout(controles)
        layout_controles.setContentsMargins(16, 12, 16, 12)
        label_station = QLabel("Station :")
        label_station.setStyleSheet("color: #5d6d7e; font-size: 13px; font-weight: 600; border: none; background: transparent;")
        layout_controles.addWidget(label_station)
        self.combo_station = QComboBox()
        self.combo_station.setMinimumWidth(260)
        self.combo_station.setStyleSheet("""
            QComboBox { padding: 6px 10px; border: 1px solid #dfe4ea; border-radius: 6px; background: white; color: #2c3e50; }
        """)
        self.combo_station.currentIndexChanged.connect(self._rafraichir)
        layout_controles.addWidget(self.combo_station)
        layout_controles.addStretch()
        layout.addWidget(controles)

        layout.addWidget(self._label_section("Alertes météo"))
        self.zone_alertes = QVBoxLayout()
        self.zone_alertes.setSpacing(8)
        layout.addLayout(self.zone_alertes)

        layout.addWidget(self._label_section("Indicateurs du jour"))
        self.grille_cartes = QGridLayout()
        self.grille_cartes.setSpacing(14)
        self.grille_cartes.setColumnStretch(0, 1)
        self.grille_cartes.setColumnStretch(1, 1)
        self.grille_cartes.setColumnStretch(2, 1)
        self.grille_cartes.setColumnStretch(3, 1)
        layout.addLayout(self.grille_cartes)

        layout.addWidget(self._label_section("Historique (30 derniers jours)"))
        self.tableau = QTableWidget()
        colonnes = ["Date", "Cumul pluie 7j", "Cumul pluie 30j", "Bilan hydrique 7j", "Jours sans pluie", "Gel", "Stress thermique", "GDD cumulé"]
        self.tableau.setColumnCount(len(colonnes))
        self.tableau.setHorizontalHeaderLabels(colonnes)
        self.tableau.verticalHeader().setVisible(False)
        self.tableau.verticalHeader().setDefaultSectionSize(34)
        self.tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau.setSelectionMode(QAbstractItemView.NoSelection)
        self.tableau.setAlternatingRowColors(True)
        self.tableau.setShowGrid(False)
        self.tableau.setFixedHeight(360)
        self.tableau.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header = self.tableau.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(90)
        self.tableau.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 10px; color: #2c3e50; border: none; font-size: 12.5px; }
            QTableWidget::item { padding: 6px; border: none; }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 9px 6px; border: none; font-weight: bold; font-size: 12px; }
        """)
        layout.addWidget(self.tableau)

        layout.addWidget(self._label_section("Anomalies capteur détectées"))
        self.zone_anomalies = QVBoxLayout()
        self.zone_anomalies.setSpacing(6)
        layout.addLayout(self.zone_anomalies)

    # ------------------------------------------------------------------
    # Rafraîchissement
    # ------------------------------------------------------------------

    def rafraichir(self):
        """Point d'entrée public : bouton Actualiser, minuteur auto, et event_bus."""
        self._rafraichir()
        self.label_derniere_maj.setText(f"Mis à jour : {datetime.now().strftime('%H:%M:%S')}")

    def _demarrer_actualisation_auto(self):
        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self.rafraichir)
        self._minuteur.start(5 * 60 * 1000)

    def rafraichir_donnees(self):
        self.rafraichir()

    def _rafraichir(self):
        if self.combo_station.count() == 0:
            return

        station_id = self.combo_station.currentData()
        session = SessionLocal()

        dernier = session.query(IndicateurJournalier).filter_by(
            station_id=station_id
        ).order_by(IndicateurJournalier.date.desc()).first()

        historique = session.query(IndicateurJournalier).filter(
            IndicateurJournalier.station_id == station_id,
            IndicateurJournalier.date >= date.today() - timedelta(days=30)
        ).order_by(IndicateurJournalier.date.desc()).all()

        derniere_mesure = session.query(Mesure).filter_by(
            station_id=station_id
        ).order_by(Mesure.date_heure.desc()).first()

        mesures_historique = session.query(Mesure).filter(
            Mesure.station_id == station_id,
            Mesure.date_heure >= date.today() - timedelta(days=30)
        ).order_by(Mesure.date_heure).all()

        session.close()

        self._afficher_alertes(derniere_mesure)
        self._afficher_cartes(dernier)
        self._afficher_historique(historique)
        self._afficher_anomalies(mesures_historique)

    def _label_section(self, texte):
        label = QLabel(texte)
        label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px; margin-top: 6px;")
        return label

    def _style_bouton(self, couleur, couleur_hover):
        return f"""
            QPushButton {{ background-color: {couleur}; color: white; border-radius: 6px; padding: 9px 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {couleur_hover}; }}
            QPushButton:disabled {{ background-color: #bdc3c7; }}
        """

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

    def _rgba(self, couleur_hex, alpha=0.12):
        couleur_hex = couleur_hex.lstrip("#")
        r = int(couleur_hex[0:2], 16)
        g = int(couleur_hex[2:4], 16)
        b = int(couleur_hex[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

    def _basculer_panneau_info(self):
        self.panneau_info.setVisible(not self.panneau_info.isVisible())

    def _charger_stations_dans_combo(self):
        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).order_by(Station.nom).all()
        session.close()

        self.combo_station.blockSignals(True)
        self.combo_station.clear()
        for station in stations:
            self.combo_station.addItem(f"{station.code} - {station.nom}", station.id)
        self.combo_station.blockSignals(False)

    def _recalculer(self):
        self.bouton_recalculer.setEnabled(False)
        self.label_statut.setText("Calcul en cours...")

        self.worker = IndicateursWorker()
        self.worker.ligne_log.connect(lambda texte: self.label_statut.setText(texte))
        self.worker.termine.connect(self._recalcul_termine)
        self.worker.start()

    def _recalcul_termine(self, total):
        self.label_statut.setText(f"Calcul terminé : {total} indicateur(s) mis à jour.")
        self.bouton_recalculer.setEnabled(True)
        self._rafraichir()

    # ------------------------------------------------------------------
    # Alertes météo
    # ------------------------------------------------------------------

    def _creer_bandeau(self, icone, texte, couleur, texte_couleur=None, word_wrap=False):
        texte_couleur = texte_couleur or couleur
        bandeau = QFrame()
        bandeau.setStyleSheet(f"""
            QFrame {{
                background-color: {self._rgba(couleur, 0.10)};
                border-left: 4px solid {couleur};
                border-radius: 8px;
            }}
        """)
        bandeau.setMinimumHeight(40)
        l = QHBoxLayout(bandeau)
        l.setContentsMargins(14, 10, 14, 10)
        label = QLabel(f"{icone}  {texte}")
        label.setStyleSheet(f"color: {texte_couleur}; font-weight: 600; font-size: 13px; border: none; background: transparent;")
        label.setWordWrap(word_wrap)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        l.addWidget(label)
        l.addStretch()
        return bandeau

    def _afficher_alertes(self, derniere_mesure):
        while self.zone_alertes.count():
            item = self.zone_alertes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not derniere_mesure:
            self.zone_alertes.addWidget(
                self._creer_bandeau("ℹ", "Aucune donnée disponible pour cette station.", "#7f8c8d")
            )
            return

        temp_max = derniere_mesure.temperature_max
        vent_vitesse = derniere_mesure.vent
        humidite = derniere_mesure.humidite

        alertes = detecter_alertes(temp_max, vent_vitesse, humidite)

        if not alertes:
            self.zone_alertes.addWidget(
                self._creer_bandeau("✅", "Aucune alerte active", "#27ae60", "#1e8449")
            )
            return

        for alerte in alertes:
            self.zone_alertes.addWidget(
                self._creer_bandeau(alerte.icone, alerte.message, alerte.couleur)
            )

    # ------------------------------------------------------------------
    # Cartes indicateurs
    # ------------------------------------------------------------------

    def _afficher_cartes(self, dernier):
        while self.grille_cartes.count():
            item = self.grille_cartes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not dernier:
            label = QLabel("Aucun indicateur calculé pour cette station. Clique sur « Recalculer maintenant ».")
            label.setStyleSheet("color: #7f8c8d; font-size: 13px;")
            self.grille_cartes.addWidget(label, 0, 0, 1, 4)
            return

        cartes = [
            ("🌧", "Cumul pluie (7j)", f"{dernier.cumul_pluie_7j:.1f} mm" if dernier.cumul_pluie_7j is not None else "—", "#1a5276"),
            ("🌧", "Cumul pluie (30j)", f"{dernier.cumul_pluie_30j:.1f} mm" if dernier.cumul_pluie_30j is not None else "—", "#2980b9"),
            ("💧", "Bilan hydrique (7j)", f"{dernier.bilan_hydrique_7j:+.1f} mm" if dernier.bilan_hydrique_7j is not None else "—",
             "#27ae60" if (dernier.bilan_hydrique_7j or 0) >= 0 else "#c0392b"),
            ("☀", "Jours sans pluie", str(dernier.jours_sans_pluie) if dernier.jours_sans_pluie is not None else "—", "#e67e22"),
            ("❄", "Gel détecté", "Oui" if dernier.gel_detecte else "Non", "#c0392b" if dernier.gel_detecte else "#27ae60"),
            ("🌡", "Stress thermique", "Oui" if dernier.stress_thermique else "Non", "#c0392b" if dernier.stress_thermique else "#27ae60"),
            ("🌱", "GDD cumulé (saison)", f"{dernier.gdd_cumule_saison:.0f}" if dernier.gdd_cumule_saison is not None else "—", "#8e44ad"),
        ]

        for i, (icone, titre, valeur, couleur) in enumerate(cartes):
            self.grille_cartes.addWidget(self._creer_carte(icone, titre, valeur, couleur), i // 4, i % 4)

    def _creer_carte(self, icone, titre, valeur, couleur):
        carte = QFrame()
        carte.setStyleSheet("QFrame { background-color: white; border-radius: 12px; border: 1px solid #eef0f2; }")
        carte.setGraphicsEffect(self._ombre_legere())
        carte.setMinimumHeight(96)

        layout = QHBoxLayout(carte)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        badge = QLabel(icone)
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {self._rgba(couleur, 0.12)};
                border-radius: 22px;
                font-size: 19px;
                border: none;
            }}
        """)
        layout.addWidget(badge)

        bloc_texte = QVBoxLayout()
        bloc_texte.setSpacing(2)

        label_valeur = QLabel(valeur)
        label_valeur.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {couleur}; border: none; background: transparent;")
        bloc_texte.addWidget(label_valeur)

        label_titre = QLabel(titre)
        label_titre.setStyleSheet("color: #8592a3; font-size: 11.5px; border: none; background: transparent;")
        label_titre.setWordWrap(True)
        bloc_texte.addWidget(label_titre)

        layout.addLayout(bloc_texte, 1)

        return carte

    # ------------------------------------------------------------------
    # Historique
    # ------------------------------------------------------------------

    def _afficher_historique(self, historique):
        self.tableau.setRowCount(len(historique))
        for i, ind in enumerate(historique):
            valeurs = [
                ind.date.strftime("%d/%m/%Y"),
                f"{ind.cumul_pluie_7j:.1f}" if ind.cumul_pluie_7j is not None else "—",
                f"{ind.cumul_pluie_30j:.1f}" if ind.cumul_pluie_30j is not None else "—",
                f"{ind.bilan_hydrique_7j:+.1f}" if ind.bilan_hydrique_7j is not None else "—",
                str(ind.jours_sans_pluie) if ind.jours_sans_pluie is not None else "—",
                "Oui" if ind.gel_detecte else "Non",
                "Oui" if ind.stress_thermique else "Non",
                f"{ind.gdd_cumule_saison:.0f}" if ind.gdd_cumule_saison is not None else "—",
            ]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                item.setTextAlignment(Qt.AlignCenter if col > 0 else Qt.AlignLeft | Qt.AlignVCenter)
                item.setForeground(QColor("#2c3e50"))
                self.tableau.setItem(i, col, item)

    # ------------------------------------------------------------------
    # Détection d'anomalies capteur
    # ------------------------------------------------------------------

    def _afficher_anomalies(self, mesures_historique):
        while self.zone_anomalies.count():
            item = self.zone_anomalies.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not mesures_historique:
            label = QLabel("Aucune donnée disponible pour cette station.")
            label.setStyleSheet("color: #7f8c8d; font-size: 12px; font-style: italic;")
            self.zone_anomalies.addWidget(label)
            return

        valeurs = [m.temperature_max for m in mesures_historique]
        anomalies_regles = detecter_anomalies_temperature(valeurs)

        station_id = self.combo_station.currentData()
        anomalies_ml = detecter_anomalies_mesures(mesures_historique, station_id)

        if not anomalies_regles and not anomalies_ml:
            label = QLabel("Aucune anomalie détectée sur les 30 derniers jours.")
            label.setStyleSheet("color: #7f8c8d; font-size: 12px; font-style: italic;")
            self.zone_anomalies.addWidget(label)
            return

        for a in anomalies_regles:
            date_mesure = mesures_historique[a.index].date_heure.strftime("%d/%m/%Y")
            self.zone_anomalies.addWidget(
                self._creer_bandeau("⚠", f"{date_mesure} — valeur {a.valeur:.1f}°C : {a.raison}", "#c0392b", word_wrap=True)
            )

        for mesure, score in anomalies_ml:
            date_mesure = mesure.date_heure.strftime("%d/%m/%Y")
            details = (
                f"T={mesure.temperature}, Tmin={mesure.temperature_min}, Tmax={mesure.temperature_max}, "
                f"HR={mesure.humidite}, Pluie={mesure.pluie}mm"
            )
            self.zone_anomalies.addWidget(
                self._creer_bandeau(
                    "🤖", f"{date_mesure} — anomalie détectée par IA (score {score:.2f}) : {details}",
                    "#8e44ad", word_wrap=True
                )
            )