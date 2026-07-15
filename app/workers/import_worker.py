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
        from app.services.calcul_indicateurs import calculer_indicateurs

        total = importer_fichier(self.chemin_fichier, log=self.ligne_log.emit)
        # Sans ça, les nouvelles mesures restent invisibles des indicateurs tant que la
        # tâche 6h ou un recalcul manuel n'est pas déclenché ailleurs.
        calculer_indicateurs(log=self.ligne_log.emit)
        self.termine.emit(total)

class IndicateursWorker(QThread):
    ligne_log = Signal(str)
    termine = Signal(int)

    def run(self):
        from app.services.calcul_indicateurs import calculer_indicateurs
        total = calculer_indicateurs(log=self.ligne_log.emit)
        self.termine.emit(total)

class TacheQuotidienneWorker(QThread):
    ligne_log = Signal(str)
    termine = Signal()

    def run(self):
        import builtins
        ancien_print = builtins.print
        builtins.print = lambda *args, **kwargs: self.ligne_log.emit(" ".join(str(a) for a in args))

        try:
            from app.services.scheduler import tache_quotidienne_6h
            tache_quotidienne_6h()
        finally:
            builtins.print = ancien_print

        self.termine.emit()