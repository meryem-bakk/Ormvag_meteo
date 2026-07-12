from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from datetime import datetime

from app.database import SessionLocal
from app.models.station import Station
from app.services.prevision_ml import prevoir_station, modele_disponible


class PrevisionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self._build_ui()
        self._rafraichir()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        entete = QHBoxLayout()
        titre = QLabel("Prévisions météo (J+1)")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        entete.addWidget(titre)
        entete.addStretch()

        bouton_actualiser = QPushButton("🔄 Actualiser")
        bouton_actualiser.setCursor(Qt.PointingHandCursor)
        bouton_actualiser.setStyleSheet("""
            QPushButton { background-color: white; color: #1a5276; border: 1px solid #d5dbdb; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #eaf2f8; }
        """)
        bouton_actualiser.clicked.connect(self._rafraichir)
        entete.addWidget(bouton_actualiser)
        layout.addLayout(entete)

        self.label_note = QLabel(
            "Modèle LSTM entraîné sur l'historique des stations. À titre indicatif : erreur moyenne "
            "d'environ 1,1°C sur la température, et la quantité de pluie prévue est souvent sous-estimée "
            "lors des épisodes pluvieux — se fier surtout à la tendance (pluie oui/non) plutôt qu'au chiffre exact."
        )
        self.label_note.setStyleSheet("color: #7f8c8d; font-size: 11.5px; font-style: italic;")
        self.label_note.setWordWrap(True)
        layout.addWidget(self.label_note)

        self.label_statut = QLabel("")
        self.label_statut.setStyleSheet("color: #c0392b; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.label_statut)

        cadre_tableau = QFrame()
        cadre_tableau.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        cadre_tableau.setGraphicsEffect(self._ombre_legere())
        layout_cadre = QVBoxLayout(cadre_tableau)
        layout_cadre.setContentsMargins(4, 4, 4, 4)

        self.tableau = QTableWidget()
        colonnes = ["Station", "Province", "Date prévue", "Pluie prévue (mm)", "Température prévue (°C)"]
        self.tableau.setColumnCount(len(colonnes))
        self.tableau.setHorizontalHeaderLabels(colonnes)
        self.tableau.verticalHeader().setVisible(False)
        self.tableau.verticalHeader().setDefaultSectionSize(34)
        self.tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau.setSelectionMode(QTableWidget.NoSelection)
        self.tableau.setAlternatingRowColors(True)
        header = self.tableau.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.tableau.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 10px; color: #2c3e50; border: none; font-size: 12.5px; }
            QTableWidget::item { padding: 6px; border: none; }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 9px 6px; border: none; font-weight: bold; font-size: 12px; }
        """)
        layout_cadre.addWidget(self.tableau)
        layout.addWidget(cadre_tableau, 1)

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

    def rafraichir_donnees(self):
        self._rafraichir()

    def _rafraichir(self):
        if not modele_disponible():
            self.label_statut.setText(
                "Modèle de prévision indisponible sur ce poste (fichiers ML/modele_lstm.keras "
                "et ML/parametres_lstm.npz non trouvés)."
            )
            self.tableau.setRowCount(0)
            return

        self.label_statut.setText("")

        session = SessionLocal()
        stations = session.query(Station).filter_by(actif=True).order_by(Station.province, Station.nom).all()

        lignes = []
        for station in stations:
            prevision = prevoir_station(session, station)
            lignes.append((station, prevision))

        session.close()

        self.tableau.setRowCount(len(lignes))
        for i, (station, prevision) in enumerate(lignes):
            if prevision is None:
                valeurs = [station.nom, station.province or "—", "—", "Historique insuffisant", "—"]
            else:
                valeurs = [
                    station.nom,
                    station.province or "—",
                    prevision["date"].strftime("%d/%m/%Y"),
                    f"{max(prevision['pluie'], 0):.1f}",
                    f"{prevision['temperature']:.1f}",
                ]

            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                item.setTextAlignment(Qt.AlignCenter if col > 0 else Qt.AlignLeft | Qt.AlignVCenter)
                item.setForeground(QColor("#2c3e50") if prevision is not None else QColor("#95a5a6"))
                self.tableau.setItem(i, col, item)
