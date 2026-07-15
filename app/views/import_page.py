from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog
)
from PySide6.QtCore import Qt
from app.workers.import_worker import ImportManuelWorker, TacheQuotidienneWorker
from app.utils.event_bus import event_bus
from app.utils.theme import COULEURS, titre_section


class ImportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COULEURS['fond']};")
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        titre = QLabel("Import des données")
        titre.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COULEURS['texte']};")
        layout.addWidget(titre)

        # --- Tâche complète (import + indicateurs) ---
        bloc_titre_tache, _ = titre_section("Tâche quotidienne complète (normalement automatique à 6h00)")
        layout.addLayout(bloc_titre_tache)

        description_tache = QLabel(
            "Exécute manuellement l'import + le calcul des indicateurs, puis rafraîchit toutes "
            "les pages — utile pour tester sans attendre 6h du matin."
        )
        description_tache.setStyleSheet(
            f"color: {COULEURS['neutre']}; font-size: 12px; border: none; background: transparent;"
        )
        description_tache.setWordWrap(True)
        layout.addWidget(description_tache)

        ligne_tache = QHBoxLayout()
        self.bouton_tache_complete = QPushButton("Exécuter maintenant")
        self.bouton_tache_complete.setCursor(Qt.PointingHandCursor)
        self.bouton_tache_complete.setStyleSheet(self._style_bouton("#8e44ad", "#6c3483"))
        self.bouton_tache_complete.clicked.connect(self._lancer_tache_complete)
        ligne_tache.addWidget(self.bouton_tache_complete)
        ligne_tache.addStretch()
        layout.addLayout(ligne_tache)

        # --- Import manuel ---
        bloc_titre_manuel, _ = titre_section("Import manuel — fichier Excel")
        layout.addLayout(bloc_titre_manuel)

        description_manuel = QLabel("Sélectionne un fichier Excel déjà exporté depuis le site (station par station).")
        description_manuel.setStyleSheet(
            f"color: {COULEURS['neutre']}; font-size: 12px; border: none; background: transparent;"
        )
        layout.addWidget(description_manuel)

        ligne_manuel = QHBoxLayout()
        self.bouton_choisir_fichier = QPushButton("Choisir un fichier...")
        self.bouton_choisir_fichier.setCursor(Qt.PointingHandCursor)
        self.bouton_choisir_fichier.setStyleSheet(self._style_bouton("#27ae60", "#1e8449"))
        self.bouton_choisir_fichier.clicked.connect(self._choisir_et_importer_fichier)
        ligne_manuel.addWidget(self.bouton_choisir_fichier)
        ligne_manuel.addStretch()
        layout.addLayout(ligne_manuel)

        # --- Journal ---
        bloc_titre_journal, _ = titre_section("Journal d'import")
        layout.addLayout(bloc_titre_journal)

        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setStyleSheet("""
            QTextEdit {
                background-color: #1e2b38; color: #d6eaf8;
                border-radius: 6px; padding: 10px;
                font-family: Consolas, monospace; font-size: 12px;
            }
        """)
        layout.addWidget(self.journal, stretch=1)

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
        self._ajouter_log(f"\nImport terminé : {total} mesure(s), indicateurs recalculés, "
                           f"toutes les pages ont été rafraîchies.")
        self.bouton_tache_complete.setEnabled(True)
        self.bouton_choisir_fichier.setEnabled(True)
        event_bus.donnees_mises_a_jour.emit()