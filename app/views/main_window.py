from app.views.carte_page import CartePage
from app.views.dashboard_page import DashboardPage
from app.views.utilisateurs_page import UtilisateursPage
from app.views.stations_page import StationsPage
from app.views.graphiques_page import GraphiquesPage
from app.views.donnees_page import DonneesPage
from app.views.import_page import ImportPage
from app.views.indicateurs_page import IndicateursPage
from app.views.rapports_page import RapportsPage
from app.views.parametres_page import ParametresPage
from app.utils.event_bus import event_bus
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self, utilisateur):
        super().__init__()
        self.utilisateur = utilisateur
        self.setWindowTitle("ORMVAG Météo Manager")
        self.resize(1200, 750)
        self._build_ui()

    def _build_ui(self):
        conteneur = QWidget()
        layout_principal = QHBoxLayout(conteneur)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #1a5276;")
        layout_sidebar = QVBoxLayout(sidebar)
        layout_sidebar.setContentsMargins(0, 20, 0, 20)
        layout_sidebar.setSpacing(4)

        titre = QLabel("ORMVAG\nMETEO MANAGER")
        titre.setStyleSheet("color: white; font-weight: bold; font-size: 14px; padding: 0 16px 20px 16px;")
        layout_sidebar.addWidget(titre)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: #f4f6f8;")
        self.boutons_sidebar = []
        self.bouton_sidebar_actif = None

        pages_navigation = [
            "Tableau de bord",
            "Import des données",
            "Stations",
            "Données",
            "Graphiques",
            "Indicateurs agroclimatiques",
            "Carte",
            "Rapports",
            "Utilisateurs",
            "Paramètres",
        ]

        self.pages_refs = {}
        for nom_page in pages_navigation:
            bouton = QPushButton(nom_page)
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.setStyleSheet(self._style_bouton_sidebar(False))
            bouton.clicked.connect(lambda checked=False, i=self.pages.count(), btn=bouton: self._changer_page(i, btn))
            layout_sidebar.addWidget(bouton)
            self.boutons_sidebar.append(bouton)

            if nom_page == "Tableau de bord":
                page = DashboardPage()
            elif nom_page == "Stations":
                page = StationsPage()
            elif nom_page == "Graphiques":
                page = GraphiquesPage()
            elif nom_page == "Données":
                page = DonneesPage()
            elif nom_page == "Utilisateurs":
                page = UtilisateursPage(self.utilisateur)
            elif nom_page == "Carte":
                page = CartePage()
            elif nom_page == "Import des données":
                page = ImportPage()
            elif nom_page == "Indicateurs agroclimatiques":
                page = IndicateursPage()
            elif nom_page == "Rapports":
                page = RapportsPage()
            elif nom_page == "Paramètres":
                page = ParametresPage(self.utilisateur)
                self.pages_refs[nom_page] = page
            else:
                page = self._creer_page_vide(nom_page)
            self.pages.addWidget(page)
        self.label_derniere_maj = QLabel("Dernière mise à jour auto : jamais")
        self.label_derniere_maj.setStyleSheet("color: #85a9c4; font-size: 10px; padding: 4px 16px;")
        self.label_derniere_maj.setWordWrap(True)
        layout_sidebar.addWidget(self.label_derniere_maj)

        event_bus.donnees_mises_a_jour.connect(self._rafraichir_toutes_les_pages)

        layout_sidebar.addStretch()

        info_utilisateur = QLabel(f"Connecté : {self.utilisateur.username}")
        info_utilisateur.setStyleSheet("color: #cdd9e5; font-size: 11px; padding: 8px 16px;")
        layout_sidebar.addWidget(info_utilisateur)

        layout_principal.addWidget(sidebar)
        layout_principal.addWidget(self.pages)

        self.setCentralWidget(conteneur)
        self._changer_page(0, self.boutons_sidebar[0])
    
    def _rafraichir_toutes_les_pages(self):
        for nom_page, page in self.pages_refs.items():
            if hasattr(page, "rafraichir_donnees"):
                try:
                    page.rafraichir_donnees()
                except Exception as e:
                    print(f"Erreur lors du rafraîchissement de la page '{nom_page}' : {e}")

        self.label_derniere_maj.setText(
            f"Dernière mise à jour auto : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

    def _changer_page(self, index, bouton):
        self.pages.setCurrentIndex(index)
        if self.bouton_sidebar_actif is not None and self.bouton_sidebar_actif is not bouton:
            self.bouton_sidebar_actif.setStyleSheet(self._style_bouton_sidebar(False))
        bouton.setStyleSheet(self._style_bouton_sidebar(True))
        self.bouton_sidebar_actif = bouton

    def _style_bouton_sidebar(self, actif):
        if actif:
            return """
                QPushButton {
                    background-color: #154360;
                    color: white;
                    text-align: left;
                    padding: 12px 16px;
                    border: none;
                    font-size: 13px;
                    font-weight: bold;
                }
            """
        return """
            QPushButton {
                background-color: transparent;
                color: #d6e4f0;
                text-align: left;
                padding: 12px 16px;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #154360;
                color: white;
            }
        """

    def _creer_page_vide(self, titre):
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(titre)
        label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50; padding: 24px;")
        layout.addWidget(label)
        layout.addStretch()
        return page