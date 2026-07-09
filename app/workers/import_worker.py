from PySide6.QtCore import QThread, Signal


class ImportAutoWorker(QThread):
    ligne_log = Signal(str)
    termine = Signal(int, int)

    def __init__(self, jours):
        super().__init__()
        self.jours = jours

    def run(self):
        from import_automatique import lancer_import_complet
        total, erreurs = lancer_import_complet(jours_a_recuperer=self.jours, log=self.ligne_log.emit)
        self.termine.emit(total, len(erreurs))


class ImportManuelWorker(QThread):
    ligne_log = Signal(str)
    termine = Signal(int)

    def __init__(self, chemin_fichier):
        super().__init__()
        self.chemin_fichier = chemin_fichier

    def run(self):
        from importer_donnees_reelles import importer_fichier
        total = importer_fichier(self.chemin_fichier, log=self.ligne_log.emit)
        self.termine.emit(total)

class IndicateursWorker(QThread):
    ligne_log = Signal(str)
    termine = Signal(int)

    def run(self):
        from app.services.calcul_indicateurs import calculer_indicateurs
        total = calculer_indicateurs(log=self.ligne_log.emit)
        self.termine.emit(total)