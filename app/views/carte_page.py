from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, QTimer
from datetime import datetime
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


class CartePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self._build_ui()
        self._demarrer_actualisation_auto()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        entete = QHBoxLayout()
        titre = QLabel("Carte des stations")
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

        self.vue_web = QWebEngineView()
        layout.addWidget(self.vue_web)

        self.rafraichir()

    def rafraichir(self):
        html = self._generer_html_carte()
        self.vue_web.setHtml(html, baseUrl=QUrl("https://ormvag.local/"))
        self.label_derniere_maj.setText(f"Mis à jour : {datetime.now().strftime('%H:%M:%S')}")

    def _demarrer_actualisation_auto(self):
        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self.rafraichir)
        self._minuteur.start(5 * 60 * 1000)

    def rafraichir_donnees(self):
        self.rafraichir()

    def _recuperer_stations_avec_derniere_mesure(self):
        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).all()

        donnees = []
        for station in stations:
            derniere_mesure = session.query(Mesure).filter_by(
                station_id=station.id
            ).order_by(Mesure.date_heure.desc()).first()

            donnees.append({
                "nom": station.nom,
                "code": station.code,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "derniere_mesure": derniere_mesure.date_heure.strftime("%d/%m/%Y %H:%M") if derniere_mesure else "Aucune donnée",
                "temperature": f"{derniere_mesure.temperature:.1f} °C" if derniere_mesure and derniere_mesure.temperature is not None else "—",
            })

        session.close()
        return donnees

    def _generer_html_carte(self):
        stations = self._recuperer_stations_avec_derniere_mesure()

        if stations:
            centre_lat = sum(s["latitude"] for s in stations) / len(stations)
            centre_lon = sum(s["longitude"] for s in stations) / len(stations)
        else:
            centre_lat, centre_lon = 34.26, -6.58

        marqueurs_js = ""
        for s in stations:
            popup_html = (
                f"<b>{s['code']} - {s['nom']}</b><br>"
                f"Dernière mesure : {s['derniere_mesure']}<br>"
                f"Température : {s['temperature']}"
            ).replace("'", "\\'")

            marqueurs_js += f"""
                L.marker([{s['latitude']}, {s['longitude']}])
                    .addTo(map)
                    .bindPopup('{popup_html}');
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
            var map = L.map('carte').setView([{centre_lat}, {centre_lon}], 9);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);
            {marqueurs_js}
        </script>
        </body></html>
        """