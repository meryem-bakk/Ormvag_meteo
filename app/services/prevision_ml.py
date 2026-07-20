"""Prévision météo à J+1 (pluie, température) par LSTM multi-stations.

Le modèle est entraîné hors-ligne par ML/entrainer_lstm.py et sauvegardé dans
ML/modele_lstm.keras (fichier non versionné, régénérable). Les paramètres de
normalisation nécessaires à l'inférence sont dans ML/parametres_lstm.npz (petit
fichier versionné). Si l'un des deux est absent, la prévision est indisponible
sans erreur bloquante pour le reste de l'application.
"""
import math
import os
import sys
from datetime import timedelta

import numpy as np
import requests

# Doit rester strictement identique a DEGRES_DIRECTION dans ML/preparer_donnees_lstm.py
# (encodage utilise a l'entrainement) : un decalage entre les deux fausserait les
# predictions silencieusement.
_DEGRES_DIRECTION = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}

_COLONNES_EXTERNES = ("pression_msl", "nebulosite")
_URL_ARCHIVE_METEO = "https://archive-api.open-meteo.com/v1/archive"


def _recuperer_meteo_externe(latitude, longitude, date_debut, date_fin, log=print):
    """Pression/nebulosite (absentes du site ORMVAG) pour la fenetre d'inference, via
    Open-Meteo (meme source que ML/telecharger_meteo_externe.py, utilisee a l'entrainement).
    Retourne {date: {"pression_msl": ..., "nebulosite": ...}}, ou {} si indisponible
    (pas de connexion, API en panne) - la prevision utilise alors 0.0 pour ces features."""
    try:
        reponse = requests.get(_URL_ARCHIVE_METEO, params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": date_debut.isoformat(),
            "end_date": date_fin.isoformat(),
            "daily": "surface_pressure_mean,cloud_cover_mean",
            "timezone": "Africa/Casablanca",
        }, timeout=15)
        reponse.raise_for_status()
        donnees = reponse.json()["daily"]
        return {
            date_str: {"pression_msl": pression, "nebulosite": nebulosite}
            for date_str, pression, nebulosite in zip(
                donnees["time"], donnees["surface_pressure_mean"], donnees["cloud_cover_mean"])
        }
    except Exception as e:
        log(f"[prevision_ml] Meteo externe (pression/nebulosite) indisponible : {e}")
        return {}


def _valeur_feature(mesure, colonne, meteo_externe_du_jour=None):
    """Calcule la valeur d'une feature pour une mesure donnee - reproduit exactement
    l'encodage de ML/preparer_donnees_lstm.py (colonnes brutes + vent_dir_sin/cos +
    jour_sin/cos + pression_msl/nebulosite)."""
    if colonne in _COLONNES_EXTERNES:
        if not meteo_externe_du_jour:
            return 0.0
        return meteo_externe_du_jour.get(colonne, 0.0)
    if colonne == "vent_dir_sin" or colonne == "vent_dir_cos":
        degres = _DEGRES_DIRECTION.get(mesure.direction_vent)
        if degres is None:
            return 0.0
        radian = math.radians(degres)
        return math.sin(radian) if colonne == "vent_dir_sin" else math.cos(radian)
    if colonne == "jour_sin" or colonne == "jour_cos":
        jour_annee = mesure.date_heure.timetuple().tm_yday
        angle = 2 * math.pi * jour_annee / 365.25
        return math.sin(angle) if colonne == "jour_sin" else math.cos(angle)
    return getattr(mesure, colonne) or 0.0

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

    meteo_externe = {}
    if any(c in _COLONNES_EXTERNES for c in colonnes_features):
        meteo_externe = _recuperer_meteo_externe(
            station.latitude, station.longitude,
            mesures[0].date_heure.date(), mesures[-1].date_heure.date(), log=log)

    valeurs = []
    for m in mesures:
        externe_du_jour = meteo_externe.get(m.date_heure.date().isoformat())
        ligne = [_valeur_feature(m, c, externe_du_jour) for c in colonnes_features]
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
