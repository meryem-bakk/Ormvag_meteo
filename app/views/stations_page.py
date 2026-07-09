from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QDoubleSpinBox,
    QFrame, QHeaderView, QMessageBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from app.database import SessionLocal
from app.models.station import Station


class StationsPage(QWidget):
    station_ajoutee = Signal(Station)
    station_modifiee = Signal(Station)
    station_supprimee = Signal(Station)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.station_en_edition_id = None
        self.stations_cache = []
        self._build_ui()
        self._charger_stations()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # --- En-tête : titre + compteur + recherche ---
        entete = QHBoxLayout()

        bloc_titre = QVBoxLayout()
        titre = QLabel("Gestion des stations")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        bloc_titre.addWidget(titre)

        self.label_compteur = QLabel("")
        self.label_compteur.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        bloc_titre.addWidget(self.label_compteur)

        entete.addLayout(bloc_titre)
        entete.addStretch()

        self.champ_recherche = QLineEdit()
        self.champ_recherche.setPlaceholderText("🔍  Rechercher par nom ou code…")
        self.champ_recherche.setFixedWidth(260)
        self.champ_recherche.setStyleSheet("""
            QLineEdit {
                color: #2c3e50; background-color: white;
                border: 1px solid #ccc; border-radius: 18px;
                padding: 8px 14px;
            }
            QLineEdit:focus { border: 1px solid #1a5276; }
        """)
        self.champ_recherche.textChanged.connect(self._filtrer_tableau)
        entete.addWidget(self.champ_recherche)

        layout.addLayout(entete)

        # --- Formulaire ---
        formulaire = QFrame()
        formulaire.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        formulaire.setGraphicsEffect(self._ombre_legere())
        layout_form_ext = QVBoxLayout(formulaire)
        layout_form_ext.setContentsMargins(20, 16, 20, 16)
        layout_form_ext.setSpacing(10)

        self.label_mode_form = QLabel("Ajouter une station")
        self.label_mode_form.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout_form_ext.addWidget(self.label_mode_form)

        grille_form = QGridLayout()
        grille_form.setHorizontalSpacing(14)
        grille_form.setVerticalSpacing(4)

        style_champ = """
            QLineEdit, QDoubleSpinBox {
                color: #2c3e50; background-color: white;
                border: 1px solid #ccc; border-radius: 6px; padding: 7px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus { border: 1px solid #1a5276; }
        """
        style_label_champ = "color: #7f8c8d; font-size: 11px; font-weight: 600;"

        grille_form.addWidget(self._label(style_label_champ, "NOM DE LA STATION"), 0, 0)
        grille_form.addWidget(self._label(style_label_champ, "CODE"), 0, 1)
        grille_form.addWidget(self._label(style_label_champ, "LATITUDE"), 0, 2)
        grille_form.addWidget(self._label(style_label_champ, "LONGITUDE"), 0, 3)

        self.champ_nom = QLineEdit()
        self.champ_nom.setPlaceholderText("ex : Station Sidi Allal")
        self.champ_nom.setStyleSheet(style_champ)
        grille_form.addWidget(self.champ_nom, 1, 0)

        self.champ_code = QLineEdit()
        self.champ_code.setPlaceholderText("ex : S01")
        self.champ_code.setStyleSheet(style_champ)
        grille_form.addWidget(self.champ_code, 1, 1)

        self.champ_latitude = QDoubleSpinBox()
        self.champ_latitude.setRange(-90, 90)
        self.champ_latitude.setDecimals(4)
        self.champ_latitude.setStyleSheet(style_champ)
        grille_form.addWidget(self.champ_latitude, 1, 2)

        self.champ_longitude = QDoubleSpinBox()
        self.champ_longitude.setRange(-180, 180)
        self.champ_longitude.setDecimals(4)
        self.champ_longitude.setStyleSheet(style_champ)
        grille_form.addWidget(self.champ_longitude, 1, 3)

        # Boutons du formulaire, alignés sur la même ligne que les champs
        layout_boutons_form = QHBoxLayout()
        layout_boutons_form.setSpacing(8)

        self.bouton_annuler = QPushButton("Annuler")
        self.bouton_annuler.setCursor(Qt.PointingHandCursor)
        self.bouton_annuler.setStyleSheet(self._style_bouton("#95a5a6", "#7f8c8d"))
        self.bouton_annuler.clicked.connect(self._reinitialiser_formulaire)
        self.bouton_annuler.hide()
        layout_boutons_form.addWidget(self.bouton_annuler)

        self.bouton_valider = QPushButton("+ Ajouter la station")
        self.bouton_valider.setCursor(Qt.PointingHandCursor)
        self.bouton_valider.setStyleSheet(self._style_bouton("#1a5276", "#154360"))
        self.bouton_valider.clicked.connect(self._valider_formulaire)
        layout_boutons_form.addWidget(self.bouton_valider)

        conteneur_boutons = QWidget()
        conteneur_boutons.setLayout(layout_boutons_form)
        conteneur_boutons.setStyleSheet("background-color: transparent; border: none;")
        grille_form.addWidget(conteneur_boutons, 1, 4)

        grille_form.setColumnStretch(0, 2)
        grille_form.setColumnStretch(1, 1)
        grille_form.setColumnStretch(2, 1)
        grille_form.setColumnStretch(3, 1)
        grille_form.setColumnStretch(4, 1)

        layout_form_ext.addLayout(grille_form)
        layout.addWidget(formulaire)

        # --- Actions sur sélection ---
        layout_actions = QHBoxLayout()
        layout_actions.addWidget(self._label("color: #7f8c8d; font-size: 12px;", "Sélectionne une ligne dans le tableau pour la modifier ou la supprimer :"))
        layout_actions.addStretch()

        self.bouton_modifier = QPushButton("✎  Modifier")
        self.bouton_modifier.setCursor(Qt.PointingHandCursor)
        self.bouton_modifier.setStyleSheet(self._style_bouton("#e67e22", "#d35400"))
        self.bouton_modifier.clicked.connect(self._charger_dans_formulaire)
        layout_actions.addWidget(self.bouton_modifier)

        self.bouton_supprimer = QPushButton("🗑  Supprimer")
        self.bouton_supprimer.setCursor(Qt.PointingHandCursor)
        self.bouton_supprimer.setStyleSheet(self._style_bouton("#c0392b", "#a93226"))
        self.bouton_supprimer.clicked.connect(self._supprimer_station)
        layout_actions.addWidget(self.bouton_supprimer)

        layout.addLayout(layout_actions)

        # --- Tableau ---
        self.tableau = QTableWidget()
        self.tableau.setColumnCount(5)
        self.tableau.setHorizontalHeaderLabels(["ID", "Nom", "Code", "Latitude", "Longitude"])
        self.tableau.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tableau.verticalHeader().setVisible(False)
        self.tableau.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableau.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableau.setSelectionMode(QTableWidget.SingleSelection)
        self.tableau.setAlternatingRowColors(True)
        self.tableau.verticalHeader().setDefaultSectionSize(34)
        self.tableau.setStyleSheet("""
            QTableWidget {
                background-color: white; border-radius: 10px; color: #2c3e50;
                gridline-color: #ecf0f1; border: none;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:alternate { background-color: #f8f9fa; }
            QTableWidget::item:selected { background-color: #d6eaf8; color: #1a5276; }
            QHeaderView::section {
                background-color: #ecf0f1; color: #2c3e50;
                padding: 8px; border: none; font-weight: bold;
            }
        """)
        formulaire.setGraphicsEffect(self._ombre_legere())
        layout.addWidget(self.tableau)

    def _label(self, style, texte):
        label = QLabel(texte)
        label.setStyleSheet(style)
        return label

    def _ombre_legere(self):
        ombre = QGraphicsDropShadowEffect()
        ombre.setBlurRadius(16)
        ombre.setXOffset(0)
        ombre.setYOffset(2)
        ombre.setColor(QColor(0, 0, 0, 25))
        return ombre

    def _style_bouton(self, couleur, couleur_hover):
        return f"""
            QPushButton {{ background-color: {couleur}; color: white; border-radius: 6px; padding: 9px 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {couleur_hover}; }}
        """

    def _charger_stations(self):
        session = SessionLocal()
        self.stations_cache = session.query(Station).order_by(Station.id).all()
        session.close()
        self._afficher_stations(self.stations_cache)

    def _afficher_stations(self, stations):
        self.tableau.setRowCount(len(stations))
        for i, station in enumerate(stations):
            valeurs = [
                str(station.id), station.nom, station.code,
                str(station.latitude), str(station.longitude)
            ]
            for col, valeur in enumerate(valeurs):
                item = QTableWidgetItem(valeur)
                item.setForeground(QColor("#2c3e50"))
                # Right-align numeric columns (latitude, longitude)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.tableau.setItem(i, col, item)

        self.label_compteur.setText(f"{len(stations)} station(s) au total")

    def _filtrer_tableau(self, texte):
        texte = texte.strip().lower()
        if not texte:
            self._afficher_stations(self.stations_cache)
            return

        filtrees = [
            s for s in self.stations_cache
            if texte in s.nom.lower() or texte in s.code.lower()
        ]
        self._afficher_stations(filtrees)

    def _ligne_selectionnee(self):
        lignes = self.tableau.selectionModel().selectedRows()
        if not lignes:
            QMessageBox.information(self, "Aucune sélection", "Sélectionne d'abord une station dans le tableau.")
            return None
        return lignes[0].row()

    def _charger_dans_formulaire(self):
        ligne = self._ligne_selectionnee()
        if ligne is None:
            return

        station_id = int(self.tableau.item(ligne, 0).text())
        self.station_en_edition_id = station_id

        self.champ_nom.setText(self.tableau.item(ligne, 1).text())
        self.champ_code.setText(self.tableau.item(ligne, 2).text())
        self.champ_latitude.setValue(float(self.tableau.item(ligne, 3).text()))
        self.champ_longitude.setValue(float(self.tableau.item(ligne, 4).text()))

        self.label_mode_form.setText("Modifier la station sélectionnée")
        self.bouton_valider.setText("Enregistrer les modifications")
        self.bouton_annuler.show()

    def _reinitialiser_formulaire(self):
        self.station_en_edition_id = None
        self.champ_nom.clear()
        self.champ_code.clear()
        self.champ_latitude.setValue(0)
        self.champ_longitude.setValue(0)
        self.label_mode_form.setText("Ajouter une station")
        self.bouton_valider.setText("+ Ajouter la station")
        self.bouton_annuler.hide()

    def _valider_formulaire(self):
        if self.station_en_edition_id is None:
            self._ajouter_station()
        else:
            self._modifier_station()

    def _ajouter_station(self):
        nom = self.champ_nom.text().strip()
        code = self.champ_code.text().strip()

        if not nom or not code:
            QMessageBox.warning(self, "Champs manquants", "Le nom et le code sont obligatoires.")
            return

        session = SessionLocal()
        if session.query(Station).filter_by(code=code).first():
            session.close()
            QMessageBox.warning(self, "Code existant", f"Le code '{code}' est déjà utilisé.")
            return

        nouvelle_station = Station(
            nom=nom, code=code,
            latitude=self.champ_latitude.value(),
            longitude=self.champ_longitude.value(),
            actif=True
        )
        session.add(nouvelle_station)
        session.commit()
        session.close()

        self._reinitialiser_formulaire()
        self._charger_stations()
        self.station_ajoutee.emit(nouvelle_station)

    def _modifier_station(self):
        nom = self.champ_nom.text().strip()
        code = self.champ_code.text().strip()

        if not nom or not code:
            QMessageBox.warning(self, "Champs manquants", "Le nom et le code sont obligatoires.")
            return

        session = SessionLocal()
        doublon = session.query(Station).filter(
            Station.code == code, Station.id != self.station_en_edition_id
        ).first()
        if doublon:
            session.close()
            QMessageBox.warning(self, "Code existant", f"Le code '{code}' est déjà utilisé par une autre station.")
            return

        station = session.query(Station).filter_by(id=self.station_en_edition_id).first()
        station.nom = nom
        station.code = code
        station.latitude = self.champ_latitude.value()
        station.longitude = self.champ_longitude.value()
        session.commit()
        session.close()

        self._reinitialiser_formulaire()
        self._charger_stations()
        self.station_modifiee.emit(station)

    def _supprimer_station(self):
        ligne = self._ligne_selectionnee()
        if ligne is None:
            return

        station_id = int(self.tableau.item(ligne, 0).text())
        nom_station = self.tableau.item(ligne, 1).text()

        session = SessionLocal()
        from app.models.mesure import Mesure
        nb_mesures_liees = session.query(Mesure).filter_by(station_id=station_id).count()
        session.close()

        if nb_mesures_liees > 0:
            boite = QMessageBox(self)
            boite.setWindowTitle("Station avec données")
            boite.setText(
                f"« {nom_station} » a {nb_mesures_liees} mesure(s) enregistrée(s)."
            )
            boite.setInformativeText("Que veux-tu faire ?")

            bouton_desactiver = boite.addButton("Désactiver (garder les données)", QMessageBox.ActionRole)
            bouton_tout_supprimer = boite.addButton("Tout supprimer définitivement", QMessageBox.DestructiveRole)
            bouton_annuler = boite.addButton("Annuler", QMessageBox.RejectRole)

            boite.exec()
            choix = boite.clickedButton()

            if choix == bouton_desactiver:
                session = SessionLocal()
                station = session.query(Station).filter_by(id=station_id).first()
                station.actif = False
                session.commit()
                session.close()
                self._reinitialiser_formulaire()
                self._charger_stations()
                self.station_supprimee.emit(station)
                return

            elif choix == bouton_tout_supprimer:
                confirmation_finale = QMessageBox.warning(
                    self, "Confirmation finale",
                    f"Cette action va supprimer DÉFINITIVEMENT « {nom_station} » "
                    f"et ses {nb_mesures_liees} mesure(s).\n\nAucun retour en arrière possible. Confirmer ?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if confirmation_finale != QMessageBox.Yes:
                    return

                session = SessionLocal()
                session.query(Mesure).filter_by(station_id=station_id).delete()
                station = session.query(Station).filter_by(id=station_id).first()
                session.delete(station)
                session.commit()
                session.close()
                self._reinitialiser_formulaire()
                self._charger_stations()
                self.station_supprimee.emit(station)
                return

            else:
                return

        # Station sans mesures liées : suppression simple, comme avant
        confirmation = QMessageBox.question(
            self, "Confirmer la suppression",
            f"Supprimer définitivement la station « {nom_station} » ?\nCette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirmation != QMessageBox.Yes:
            return

        session = SessionLocal()
        station = session.query(Station).filter_by(id=station_id).first()
        session.delete(station)
        session.commit()
        session.close()

        self._reinitialiser_formulaire()
        self._charger_stations()
        self.station_supprimee.emit(station)