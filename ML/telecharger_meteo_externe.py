"""Telecharge, pour chaque station active, la pression atmospherique et la
nebulosite historiques depuis l'API gratuite Open-Meteo (reanalyse ERA5, sans
cle requise) - donnees absentes du site source ORMVAG mais utiles comme
signaux precurseurs d'un changement de temps pour le LSTM de prevision.

Resultat mis en cache dans meteo_externe.csv (colonnes : station_id, date,
pression_msl, nebulosite) pour eviter de retelecharger a chaque preparation
des donnees d'entrainement.
"""
import os
import sys
import time

import requests
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure
from sqlalchemy import func

URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
CHEMIN_CACHE = os.path.join(os.path.dirname(__file__), "meteo_externe.csv")


def telecharger_station(latitude, longitude, date_debut, date_fin):
    reponse = requests.get(URL_ARCHIVE, params={
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date_debut,
        "end_date": date_fin,
        "daily": "surface_pressure_mean,cloud_cover_mean",
        "timezone": "Africa/Casablanca",
    }, timeout=30)
    reponse.raise_for_status()
    donnees = reponse.json()["daily"]
    return pd.DataFrame({
        "date": donnees["time"],
        "pression_msl": donnees["surface_pressure_mean"],
        "nebulosite": donnees["cloud_cover_mean"],
    })


def telecharger_tout(log=print):
    session = SessionLocal()
    stations = session.query(Station).filter_by(actif=True).order_by(Station.id).all()

    lignes = []
    for station in stations:
        bornes = session.query(
            func.min(Mesure.date_heure), func.max(Mesure.date_heure)
        ).filter(Mesure.station_id == station.id, Mesure.type_donnee == "Mesuré").first()

        if not bornes[0]:
            continue

        date_debut = bornes[0].date().isoformat()
        # L'archive ERA5 a quelques jours de latence : demander jusqu'a aujourd'hui ne pose
        # pas de probleme, Open-Meteo omet simplement les derniers jours pas encore prets.
        date_fin = bornes[1].date().isoformat()

        log(f"{station.nom} : telechargement {date_debut} -> {date_fin}...")
        df = telecharger_station(station.latitude, station.longitude, date_debut, date_fin)
        df["station_id"] = station.id
        lignes.append(df)

        time.sleep(1)  # courtoisie envers l'API gratuite

    session.close()

    resultat = pd.concat(lignes, ignore_index=True)
    resultat = resultat[["station_id", "date", "pression_msl", "nebulosite"]]
    resultat.to_csv(CHEMIN_CACHE, index=False)
    log(f"\n{len(resultat)} ligne(s) sauvegardee(s) dans {CHEMIN_CACHE}")
    return resultat


if __name__ == "__main__":
    telecharger_tout()
