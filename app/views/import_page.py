from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSpinBox, QTextEdit, QFileDialog, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from app.workers.import_worker import ImportManuelWorker, TacheQuotidienneWorker


class ImportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f4f6f8;")
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        titre = QLabel("Import des données")
        titre.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(titre)

        # --- Bloc test tâche complète (import + indicateurs) ---
        bloc_tache = QFrame()
        bloc_tache.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        bloc_tache.setGraphicsEffect(self._ombre_legere())
        layout_tache = QVBoxLayout(bloc_tache)
        layout_tache.setContentsMargins(20, 16, 20, 16)
        layout_tache.setSpacing(10)

        label_tache = QLabel("Tâche quotidienne complète (normalement automatique à 6h00)")
        label_tache.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout_tache.addWidget(label_tache)

        description_tache = QLabel("Exécute manuellement l'import + le calcul des indicateurs, puis rafraîchit toutes les pages — utile pour tester sans attendre 6h du matin.")
        description_tache.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        description_tache.setWordWrap(True)
        layout_tache.addWidget(description_tache)

        self.bouton_tache_complete = QPushButton("Exécuter maintenant")
        self.bouton_tache_complete.setCursor(Qt.PointingHandCursor)
        self.bouton_tache_complete.setStyleSheet(self._style_bouton("#8e44ad", "#6c3483"))
        self.bouton_tache_complete.clicked.connect(self._lancer_tache_complete)
        layout_tache.addWidget(self.bouton_tache_complete)

        layout.addWidget(bloc_tache)

        # --- Bloc import manuel ---
        bloc_manuel = QFrame()
        bloc_manuel.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        bloc_manuel.setGraphicsEffect(self._ombre_legere())
        layout_manuel = QVBoxLayout(bloc_manuel)
        layout_manuel.setContentsMargins(20, 16, 20, 16)
        layout_manuel.setSpacing(10)

        label_manuel = QLabel("Import manuel — fichier Excel")
        label_manuel.setStyleSheet("font-weight: bold; color: #1a5276; font-size: 13px;")
        layout_manuel.addWidget(label_manuel)

        description_manuel = QLabel("Sélectionne un fichier Excel déjà exporté depuis le site (station par station).")
        description_manuel.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout_manuel.addWidget(description_manuel)

        ligne_manuel = QHBoxLayout()
        self.bouton_choisir_fichier = QPushButton("Choisir un fichier...")
        self.bouton_choisir_fichier.setCursor(Qt.PointingHandCursor)
        self.bouton_choisir_fichier.setStyleSheet(self._style_bouton("#27ae60", "#1e8449"))
        self.bouton_choisir_fichier.clicked.connect(self._choisir_et_importer_fichier)
        ligne_manuel.addWidget(self.bouton_choisir_fichier)
        ligne_manuel.addStretch()
        layout_manuel.addLayout(ligne_manuel)

        layout.addWidget(bloc_manuel)

        # --- Journal ---
        label_journal = QLabel("Journal d'import")
        label_journal.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px;")
        layout.addWidget(label_journal)

        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setStyleSheet("""
            QTextEdit {
                background-color: #1e2b38; color: #d6eaf8;
                border-radius: 8px; padding: 10px;
                font-family: Consolas, monospace; font-size: 12px;
            }
        """)
        layout.addWidget(self.journal, stretch=1)

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
            QPushButton:disabled {{ background-color: #bdc3c7; }}
        """

    def _ajouter_log(self, texte):
        self.journal.append(texte)
    
    def _lancer_tache_complete(self):
        self.bouton_choisir_fichier.setEnabled(False)
        self.bouton_tache_complete.setEnabled(False)
        self.journal.clear()
        self._ajouter_log("Démarrage de la tâche quotidienne complète...")

        self.worker = TacheQuotidienneWorker()
        self.worker.ligne_log.connect(self._ajouter_log)
        self.worker.termine.connect(self._tache_complete_terminee)
        self.worker.start()

    def _tache_complete_terminee(self):
        self._ajouter_log("\nTâche terminée — toutes les pages ont été rafraîchies.")
        self.bouton_choisir_fichier.setEnabled(True)
        self.bouton_tache_complete.setEnabled(True)
        
    def _choisir_et_importer_fichier(self):
        chemin, _ = QFileDialog.getOpenFileName(self, "Choisir un fichier Excel", "", "Fichiers Excel (*.xlsx)")
        if not chemin:
            return

        self.bouton_tache_complete.setEnabled(False)
        self.bouton_choisir_fichier.setEnabled(False)
        self.journal.clear()
        self._ajouter_log(f"Import du fichier : {chemin}")

        self.worker = ImportManuelWorker(chemin)
        self.worker.ligne_log.connect(self._ajouter_log)
        self.worker.termine.connect(self._import_manuel_termine)
        self.worker.start()

    def _import_manuel_termine(self, total):
        self._ajouter_log(f"\nImport terminé : {total} mesure(s).")
        self.bouton_tache_complete.setEnabled(True)
        self.bouton_choisir_fichier.setEnabled(True)