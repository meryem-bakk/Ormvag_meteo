"""Import, Stations et Données regroupées en une seule page à onglets."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from app.utils.theme import COULEURS
from app.views.import_page import ImportPage
from app.views.stations_page import StationsPage
from app.views.donnees_page import DonneesPage


class GestionDonneesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        onglets = QTabWidget()
        onglets.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background-color: {COULEURS['fond']}; }}
            QTabBar::tab {{
                background-color: white; color: {COULEURS['texte']};
                padding: 10px 20px; margin-right: 2px; font-size: 13px;
            }}
            QTabBar::tab:selected {{
                background-color: {COULEURS['primaire']}; color: white; font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{ background-color: #ecf0f1; }}
        """)

        self.page_import = ImportPage()
        self.page_stations = StationsPage()
        self.page_donnees = DonneesPage()

        onglets.addTab(self.page_import, "Import")
        onglets.addTab(self.page_stations, "Stations")
        onglets.addTab(self.page_donnees, "Données")

        layout.addWidget(onglets)

    def rafraichir_donnees(self):
        if hasattr(self.page_stations, "rafraichir_donnees"):
            self.page_stations.rafraichir_donnees()
        if hasattr(self.page_donnees, "rafraichir_donnees"):
            self.page_donnees.rafraichir_donnees()
