"""Prépare les données historiques (table mesures) pour l'entraînement d'un LSTM
multi-stations : fenêtres glissantes, segmentation aux gros trous, interpolation
des petits trous, normalisation, découpage train/val/test chronologique.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math

import numpy as np
import pandas as pd

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

# Directions relevees par les stations du reseau (voir diagnostic_qualite.py) :
# seulement 5 valeurs en pratique (N, NE, NW, SE, SW), jamais de resolution plus
# fine. Encodee en sinus/cosinus (grandeur circulaire : N et NNW doivent etre
# "proches", pas aux deux extremes d'une echelle lineaire 0-360).
# ATTENTION : cette table et l'encodage jour_sin/jour_cos ci-dessous sont
# dupliques dans app/services/prevision_ml.py (inference) et doivent rester
# strictement identiques a l'entrainement, sous peine de decalage silencieux.
DEGRES_DIRECTION = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}

COLONNES_FEATURES = [
    "eto", "pluie", "temperature_min", "temperature", "temperature_max",
    "humidite_min", "humidite", "humidite_max", "rayonnement", "vent",
    "pression_msl", "nebulosite",
    "vent_dir_sin", "vent_dir_cos", "jour_sin", "jour_cos",
]
COLONNES_CIBLES = ["pluie", "temperature", "eto"]

TAILLE_FENETRE = 30              # jours d'historique en entrée pour prédire le jour suivant
SEUIL_INTERPOLATION = 7          # trous <= 7 jours interpolés ; au-delà : segment coupé
RATIOS_SPLIT = (0.8, 0.1, 0.1)   # train / val / test, par segment, dans l'ordre chronologique

# pression_msl/nebulosite : absentes du site source ORMVAG, telechargees separement
# (reanalyse ERA5, gratuite) par ML/telecharger_meteo_externe.py - relancer ce script
# si meteo_externe.csv est absent ou trop ancien.
COLONNES_EXTERNES = ["pression_msl", "nebulosite"]
CHEMIN_METEO_EXTERNE = os.path.join(os.path.dirname(__file__), "meteo_externe.csv")
_meteo_externe = None


def _charger_meteo_externe():
    global _meteo_externe
    if _meteo_externe is None:
        if not os.path.exists(CHEMIN_METEO_EXTERNE):
            raise FileNotFoundError(
                f"{CHEMIN_METEO_EXTERNE} introuvable - lancer ML/telecharger_meteo_externe.py d'abord."
            )
        df = pd.read_csv(CHEMIN_METEO_EXTERNE, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        _meteo_externe = df.set_index(["station_id", "date"])
    return _meteo_externe


#  eto/pluie/temperatures/humidites/rayonnement/vent : colonnes brutes de Mesure.
#  vent_dir_sin/cos et jour_sin/cos sont derivees, calculees ci-dessous ; pression_msl/
#  nebulosite viennent de la fusion avec meteo_externe.csv.
COLONNES_BRUTES = [c for c in COLONNES_FEATURES if c not in
                    ("vent_dir_sin", "vent_dir_cos", "jour_sin", "jour_cos", *COLONNES_EXTERNES)]


def charger_mesures_station(session, station_id):
    """Charge uniquement les mesures réelles (pas les Prévisions) d'une station, triées par
    date, et encode la direction du vent (categorielle) en sinus/cosinus (grandeur circulaire)."""
    mesures = (
        session.query(Mesure)
        .filter(Mesure.station_id == station_id, Mesure.type_donnee == "Mesuré")
        .order_by(Mesure.date_heure)
        .all()
    )
    if not mesures:
        return pd.DataFrame()

    lignes = [
        {
            "date": m.date_heure.date(),
            **{c: getattr(m, c) for c in COLONNES_BRUTES},
            "direction_vent": m.direction_vent,
        }
        for m in mesures
    ]
    df = pd.DataFrame(lignes).drop_duplicates(subset="date").set_index("date").sort_index()

    direction_rad = np.radians(df["direction_vent"].map(DEGRES_DIRECTION))
    df["vent_dir_sin"] = np.sin(direction_rad)
    df["vent_dir_cos"] = np.cos(direction_rad)
    df = df.drop(columns=["direction_vent"])

    meteo_externe = _charger_meteo_externe()
    if station_id in meteo_externe.index.get_level_values("station_id"):
        df = df.join(meteo_externe.loc[station_id, COLONNES_EXTERNES])
    else:
        for colonne in COLONNES_EXTERNES:
            df[colonne] = np.nan

    return df


def segmenter_et_interpoler(df):
    """Reconstruit un index journalier complet, coupe la série en segments continus aux
    endroits où un trou dépasse SEUIL_INTERPOLATION jours, puis interpole les petits trous
    restants à l'intérieur de chaque segment."""
    if df.empty:
        return []

    index_complet = pd.date_range(df.index.min(), df.index.max(), freq="D").date
    df_complet = df.reindex(index_complet)

    # jour_sin/jour_cos : encodage cyclique de la saisonnalite (la pluie au Maroc est tres
    # saisonniere). Calcule directement depuis la date, donc jamais manquant meme sur un
    # jour interpole/troue - contrairement aux variables mesurees ci-dessus.
    jour_annee = pd.to_datetime(df_complet.index).dayofyear
    angle = 2 * math.pi * jour_annee / 365.25
    df_complet["jour_sin"] = np.sin(angle)
    df_complet["jour_cos"] = np.cos(angle)

    # jour_sin/jour_cos ne sont jamais manquants (derives de la date, pas de la mesure) :
    # les exclure de la detection de trou, sinon aucune ligne ne serait jamais consideree
    # manquante et la segmentation ne couperait plus jamais aux vraies pannes de longue duree.
    colonnes_a_verifier = [c for c in COLONNES_FEATURES if c not in ("jour_sin", "jour_cos")]
    est_manquant = df_complet[colonnes_a_verifier].isna().all(axis=1)

    segments_bruts = []
    debut_segment = 0
    i = 0
    n = len(df_complet)
    while i < n:
        if est_manquant.iloc[i]:
            j = i
            while j < n and est_manquant.iloc[j]:
                j += 1
            if (j - i) > SEUIL_INTERPOLATION:
                segments_bruts.append(df_complet.iloc[debut_segment:i])
                debut_segment = j
            i = j
        else:
            i += 1
    segments_bruts.append(df_complet.iloc[debut_segment:n])

    segments_valides = []
    for seg in segments_bruts:
        if len(seg) <= TAILLE_FENETRE:
            continue
        seg = seg.interpolate(method="linear", limit=SEUIL_INTERPOLATION, limit_direction="both")
        if seg.isna().any().any():
            seg = seg.dropna()
        if len(seg) > TAILLE_FENETRE:
            segments_valides.append(seg)

    return segments_valides


def construire_fenetres(segment, index_station):
    """Découpe un segment continu en fenêtres glissantes : X = TAILLE_FENETRE jours -> y = jour suivant."""
    valeurs = segment[COLONNES_FEATURES].to_numpy(dtype=float)
    cibles = segment[COLONNES_CIBLES].to_numpy(dtype=float)

    nb_fenetres = len(segment) - TAILLE_FENETRE
    X = np.stack([valeurs[i:i + TAILLE_FENETRE] for i in range(nb_fenetres)])
    y = cibles[TAILLE_FENETRE:TAILLE_FENETRE + nb_fenetres]
    idx_station = np.full(nb_fenetres, index_station)

    return X, y, idx_station


def repartir_chronologiquement(n):
    """Indices (train, val, test) dans l'ordre chronologique — pas de mélange aléatoire,
    pour ne jamais entraîner sur le futur et valider/tester sur le passé."""
    n_train = int(n * RATIOS_SPLIT[0])
    n_val = int(n * RATIOS_SPLIT[1])
    return (
        np.arange(0, n_train),
        np.arange(n_train, n_train + n_val),
        np.arange(n_train + n_val, n),
    )


def preparer(log=print):
    session = SessionLocal()
    stations = session.query(Station).filter_by(actif=True).order_by(Station.id).all()
    id_vers_index = {s.id: i for i, s in enumerate(stations)}
    noms_stations = [s.nom for s in stations]

    lots = {"train": ([], [], []), "val": ([], [], []), "test": ([], [], [])}

    for station in stations:
        df = charger_mesures_station(session, station.id)
        segments = segmenter_et_interpoler(df)

        nb_fenetres_station = 0
        for segment in segments:
            X, y, idx_station = construire_fenetres(segment, id_vers_index[station.id])
            if len(X) == 0:
                continue

            i_train, i_val, i_test = repartir_chronologiquement(len(X))
            for nom_lot, indices in (("train", i_train), ("val", i_val), ("test", i_test)):
                Xs, ys, ss = lots[nom_lot]
                Xs.append(X[indices]); ys.append(y[indices]); ss.append(idx_station[indices])
            nb_fenetres_station += len(X)

        log(f"  {station.nom:<32} : {len(segments)} segment(s) continu(s), {nb_fenetres_station} fenêtre(s)")

    session.close()

    def empiler(liste):
        return np.concatenate(liste) if liste else np.zeros((0,))

    resultat = {}
    for nom_lot, (Xs, ys, ss) in lots.items():
        resultat[f"X_{nom_lot}"] = empiler(Xs)
        resultat[f"y_{nom_lot}"] = empiler(ys)
        resultat[f"station_{nom_lot}"] = empiler(ss)

    # Normalisation : moyenne/écart-type calculés UNIQUEMENT sur le train, appliqués partout
    X_train = resultat["X_train"]
    moyenne = X_train.reshape(-1, X_train.shape[-1]).mean(axis=0)
    ecart_type = X_train.reshape(-1, X_train.shape[-1]).std(axis=0)
    ecart_type[ecart_type == 0] = 1

    for nom_lot in ("train", "val", "test"):
        X = resultat[f"X_{nom_lot}"]
        resultat[f"X_{nom_lot}"] = (X - moyenne) / ecart_type if len(X) else X

    chemin_sortie = os.path.join(os.path.dirname(__file__), "donnees_lstm.npz")
    np.savez(
        chemin_sortie,
        **resultat,
        moyenne=moyenne, ecart_type=ecart_type,
        colonnes_features=np.array(COLONNES_FEATURES),
        colonnes_cibles=np.array(COLONNES_CIBLES),
        noms_stations=np.array(noms_stations),
    )

    # Petit fichier compagnon (quelques Ko) avec uniquement ce qu'il faut pour faire
    # de l'inférence en production — contrairement à donnees_lstm.npz (fenêtres
    # d'entraînement, ~85 Mo), celui-ci peut être versionné dans le dépôt.
    chemin_params = os.path.join(os.path.dirname(__file__), "parametres_lstm.npz")
    np.savez(
        chemin_params,
        moyenne=moyenne, ecart_type=ecart_type,
        colonnes_features=np.array(COLONNES_FEATURES),
        colonnes_cibles=np.array(COLONNES_CIBLES),
        noms_stations=np.array(noms_stations),
        taille_fenetre=TAILLE_FENETRE,
    )

    log("\n=== Résumé ===")
    log(f"Train : {len(resultat['X_train'])} fenêtre(s)")
    log(f"Val   : {len(resultat['X_val'])} fenêtre(s)")
    log(f"Test  : {len(resultat['X_test'])} fenêtre(s)")
    log(f"Fichier sauvegardé : {chemin_sortie}")
    log(f"Paramètres d'inférence sauvegardés : {chemin_params}")

    return resultat


if __name__ == "__main__":
    preparer()
