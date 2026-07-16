"""Prévision météo à J+1 (pluie, température) par LSTM multi-stations.

Le modèle est entraîné hors-ligne par ML/entrainer_lstm.py et sauvegardé dans
ML/modele_lstm.keras (fichier non versionné, régénérable). Les paramètres de
normalisation nécessaires à l'inférence sont dans ML/parametres_lstm.npz (petit
fichier versionné). Si l'un des deux est absent, la prévision est indisponible
sans erreur bloquante pour le reste de l'application.
"""
import os
import sys
from datetime import timedelta

import numpy as np

# En exécutable PyInstaller, __file__ pointe vers le dossier d'extraction
# temporaire (sys._MEIPASS), pas vers le projet — les modèles doivent alors
# être cherchés à côté de l'exécutable plutôt que relativement au code source.
if getattr(sys, "frozen", False):
    _RACINE_PROJET = os.path.dirname(sys.executable)
else:
    _RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOSSIER_ML = os.path.join(_RACINE_PROJET, "ML")
CHEMIN_MODELE = os.path.join(DOSSIER_ML, "modele_lstm.keras")
CHEMIN_PARAMETRES = os.path.join(DOSSIER_ML, "parametres_lstm.npz")

_cache_modele = None
_cache_parametres = None
_absence_signalee = False


def modele_disponible():
    return os.path.exists(CHEMIN_MODELE) and os.path.exists(CHEMIN_PARAMETRES)


def _charger(log=print):
    global _cache_modele, _cache_parametres, _absence_signalee

    if _cache_modele is not None and _cache_parametres is not None:
        return _cache_modele, _cache_parametres

    if not modele_disponible():
        if not _absence_signalee:
            log(f"[prevision_ml] Modèle ou paramètres introuvables dans {DOSSIER_ML} — "
                f"prévisions désactivées. Lancer ML/preparer_donnees_lstm.py puis ML/entrainer_lstm.py pour les activer.")
            _absence_signalee = True
        return None, None

    from tensorflow import keras
    _cache_modele = keras.models.load_model(CHEMIN_MODELE)

    donnees = np.load(CHEMIN_PARAMETRES, allow_pickle=True)
    _cache_parametres = {
        "moyenne": donnees["moyenne"],
        "ecart_type": donnees["ecart_type"],
        "colonnes_features": list(donnees["colonnes_features"]),
        "colonnes_cibles": list(donnees["colonnes_cibles"]),
        "noms_stations": list(donnees["noms_stations"]),
        "taille_fenetre": int(donnees["taille_fenetre"]),
    }
    return _cache_modele, _cache_parametres


def prevoir_station(session_db, station, log=print):
    """Prévoit (pluie, température) du lendemain pour une station, à partir de ses
    dernières mesures réelles. Retourne un dict {"date", "pluie", "temperature"} ou
    None si la prévision est indisponible (modèle absent, historique insuffisant,
    ou station inconnue du modèle entraîné)."""
    from app.models.mesure import Mesure

    modele, parametres = _charger(log=log)
    if modele is None:
        return None

    noms_stations = parametres["noms_stations"]
    if station.nom not in noms_stations:
        return None
    index_station = noms_stations.index(station.nom)

    taille_fenetre = parametres["taille_fenetre"]
    colonnes_features = parametres["colonnes_features"]

    mesures = (
        session_db.query(Mesure)
        .filter(Mesure.station_id == station.id, Mesure.type_donnee == "Mesuré")
        .order_by(Mesure.date_heure.desc())
        .limit(taille_fenetre)
        .all()
    )
    if len(mesures) < taille_fenetre:
        return None
    mesures = list(reversed(mesures))  # ordre chronologique croissant

    # Vérifie la continuité : le modèle a été entraîné sur des séquences de jours
    # consécutifs, une fenêtre trouée donnerait une prévision non fiable.
    for i in range(1, len(mesures)):
        if (mesures[i].date_heure.date() - mesures[i - 1].date_heure.date()) != timedelta(days=1):
            return None

    moyenne = parametres["moyenne"]
    ecart_type = parametres["ecart_type"]

    valeurs = []
    for m in mesures:
        ligne = [getattr(m, c) or 0.0 for c in colonnes_features]
        valeurs.append(ligne)
    X = np.array(valeurs, dtype=float)
    X_norm = (X - moyenne) / ecart_type
    X_norm = X_norm.reshape(1, taille_fenetre, len(colonnes_features))

    station_idx = np.array([[index_station]], dtype="int32")

    prediction = modele.predict({"sequence": X_norm, "station": station_idx}, verbose=0)[0]

    colonnes_cibles = parametres["colonnes_cibles"]
    resultat = {"date": mesures[-1].date_heure.date() + timedelta(days=1)}
    for i, cible in enumerate(colonnes_cibles):
        resultat[cible] = float(prediction[i])

    return resultat
