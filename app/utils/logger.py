"""Journal applicatif partagé, écrit dans app.log à côté de l'exécutable.

L'application est packagée sans console (console=False, voir ORMVAG-Meteo.spec) :
un print() n'est visible nulle part une fois l'exécutable lancé normalement,
en particulier pour la tâche planifiée quotidienne (app/services/scheduler.py)
qui tourne sans qu'aucun utilisateur ne soit devant un terminal. Seul un
fichier de log survit à la fermeture de l'application. Ce journal est
volontairement distinct de erreur.log (réservé aux exceptions non interceptées
remontées jusqu'à Qt, voir main.py) : app.log trace le déroulement normal
(et les erreurs déjà interceptées) de la tâche quotidienne et de l'envoi
d'e-mail.
"""
import logging
import os
from app.utils.chemins import racine_projet

_CHEMIN_LOG = os.path.join(racine_projet(), "app.log")

logger = logging.getLogger("ormvag_meteo")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _handler = logging.FileHandler(_CHEMIN_LOG, encoding="utf-8")
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(_handler)
