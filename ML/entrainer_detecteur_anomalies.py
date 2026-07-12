"""Entraîne un détecteur d'anomalies (Isolation Forest) sur les mesures météo
réelles ("Mesuré") de toutes les stations, avec l'identité de la station comme
variable (one-hot) pour que le modèle tienne compte du climat propre à chacune.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

COLONNES_FEATURES = [
    "eto", "pluie", "temperature_min", "temperature", "temperature_max",
    "humidite_min", "humidite", "humidite_max", "rayonnement", "vent",
]
CONTAMINATION = 0.02  # proportion attendue d'anomalies (pannes/erreurs capteur rares)

DOSSIER = os.path.dirname(__file__)
CHEMIN_MODELE = os.path.join(DOSSIER, "detecteur_anomalies.joblib")


def charger_donnees(session):
    stations = session.query(Station).filter_by(actif=True).order_by(Station.id).all()
    noms_colonnes_station = [f"station_{s.id}" for s in stations]

    lignes = []
    for station in stations:
        mesures = (
            session.query(Mesure)
            .filter(Mesure.station_id == station.id, Mesure.type_donnee == "Mesuré")
            .all()
        )
        for m in mesures:
            ligne = {"station_id": station.id, "station_nom": station.nom, "date": m.date_heure.date()}
            for c in COLONNES_FEATURES:
                ligne[c] = getattr(m, c)
            lignes.append(ligne)

    df = pd.DataFrame(lignes)
    return df, [s.id for s in stations]


def construire_matrice_features(df, ids_stations):
    """Impute les valeurs manquantes (médiane par colonne) et one-hot encode la station."""
    df_features = df[COLONNES_FEATURES].copy()
    for c in COLONNES_FEATURES:
        df_features[c] = df_features[c].fillna(df_features[c].median())

    for sid in ids_stations:
        df_features[f"station_{sid}"] = (df["station_id"] == sid).astype(int)

    return df_features


def entrainer(log=print):
    session = SessionLocal()
    df, ids_stations = charger_donnees(session)
    session.close()

    log(f"{len(df)} mesure(s) chargée(s) sur {len(ids_stations)} station(s).")

    X = construire_matrice_features(df, ids_stations)

    modele = IsolationForest(
        n_estimators=200, contamination=CONTAMINATION, random_state=42, n_jobs=-1
    )
    modele.fit(X)

    scores = modele.decision_function(X)
    predictions = modele.predict(X)  # -1 = anomalie, 1 = normal

    df_resultat = df.copy()
    df_resultat["score_anomalie"] = scores
    df_resultat["est_anomalie"] = predictions == -1

    nb_anomalies = int(df_resultat["est_anomalie"].sum())
    log(f"\n{nb_anomalies} anomalie(s) détectée(s) sur {len(df_resultat)} mesure(s) "
        f"({100 * nb_anomalies / len(df_resultat):.2f}%).")

    log("\n=== 15 anomalies les plus marquées ===")
    pires = df_resultat[df_resultat["est_anomalie"]].sort_values("score_anomalie").head(15)
    colonnes_affichage = ["station_nom", "date", "score_anomalie"] + COLONNES_FEATURES
    for _, ligne in pires.iterrows():
        log(f"  {ligne['station_nom']} — {ligne['date']} (score {ligne['score_anomalie']:.3f}) : "
            f"pluie={ligne['pluie']}, T={ligne['temperature']}, "
            f"Tmin={ligne['temperature_min']}, Tmax={ligne['temperature_max']}, "
            f"HR={ligne['humidite']}, vent={ligne['vent']}")

    joblib.dump({
        "modele": modele,
        "colonnes_features": COLONNES_FEATURES,
        "ids_stations": ids_stations,
        "medianes": df[COLONNES_FEATURES].median().to_dict(),
    }, CHEMIN_MODELE)
    log(f"\nModèle sauvegardé : {CHEMIN_MODELE}")

    return df_resultat


if __name__ == "__main__":
    entrainer()
