"""Résolution du dossier racine de l'application.

Une fois l'application figée par PyInstaller, __file__ pointe vers un dossier
d'extraction temporaire et non vers l'emplacement réel des fichiers : tout
chemin construit à partir de __file__ (icône, logs, fichiers de marqueur...)
doit donc se repositionner par rapport à l'exécutable (sys.executable) plutôt
que par rapport au code source. Centralisé ici pour éviter que cette logique
ne soit dupliquée et ne diverge entre plusieurs fichiers (voir la difficulté
de packaging équivalente déjà rencontrée pour les artefacts du module ML).
"""
import os
import sys


def racine_projet():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Ce fichier est à app/utils/chemins.py : la racine du projet est trois
    # niveaux au-dessus.
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
