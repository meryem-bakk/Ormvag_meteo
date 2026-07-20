"""Typologie du reseau ORMVAG, en complement des modeles de prevision/anomalies :

1. Regroupement des stations par profil climatique (KMeans sur pluie/temperature/
   humidite/ETo moyens) - utile pour contextualiser un bulletin ("station typique
   d'un groupe plus sec/chaud") sans avoir a comparer les 14 stations une par une.
2. Classification de chaque campagne agricole (1er septembre - 31 aout) en
   seche/normale/humide, par comparaison du cumul de pluie reseau a la normale
   30 ans deja utilisee dans les rapports (app/services/generateur_rapport.py).

Scripts d'analyse ponctuelle (pas d'integration a l'app pour l'instant), a
relancer manuellement si besoin d'une typologie a jour.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure
from app.services.generateur_rapport import NORMALE_30_ANS_MENSUELLE

COLONNES_PROFIL = ["pluie_annuelle", "temperature_moyenne", "humidite_moyenne", "eto_annuel", "vent_moyen"]
NORMALE_ANNUELLE_MM = sum(NORMALE_30_ANS_MENSUELLE.values())

# Seuils usuels en agrometeorologie pour qualifier une campagne par rapport a la normale
SEUIL_SECHE = 0.70    # < 70% de la normale
SEUIL_HUMIDE = 1.30   # > 130% de la normale


def _profil_stations(session):
    """Une ligne par station : moyennes climatiques sur tout l'historique confirme."""
    stations = session.query(Station).filter_by(actif=True).order_by(Station.id).all()
    lignes = []
    for station in stations:
        mesures = (
            session.query(Mesure)
            .filter(Mesure.station_id == station.id, Mesure.type_donnee == "Mesuré")
            .all()
        )
        if not mesures:
            continue

        df = pd.DataFrame([{
            "date": m.date_heure.date(), "pluie": m.pluie or 0, "temperature": m.temperature,
            "humidite": m.humidite, "eto": m.eto or 0, "vent": m.vent,
        } for m in mesures])
        nb_annees = (df["date"].max() - df["date"].min()).days / 365.25

        lignes.append({
            "station_id": station.id,
            "nom": station.nom,
            "pluie_annuelle": df["pluie"].sum() / nb_annees,
            "temperature_moyenne": df["temperature"].mean(),
            "humidite_moyenne": df["humidite"].mean(),
            "eto_annuel": df["eto"].sum() / nb_annees,
            "vent_moyen": df["vent"].mean(),
        })
    return pd.DataFrame(lignes)


def regrouper_stations(log=print):
    session = SessionLocal()
    profils = _profil_stations(session)
    session.close()

    X = StandardScaler().fit_transform(profils[COLONNES_PROFIL])

    # Choix du nombre de groupes par score de silhouette (2 a 5, borne haute raisonnable
    # vu qu'on n'a que 14 stations) plutot qu'une valeur arbitraire fixee a l'avance.
    meilleur_k, meilleur_score = None, -1
    for k in range(2, 6):
        etiquettes = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
        score = silhouette_score(X, etiquettes)
        log(f"  k={k} : score de silhouette = {score:.3f}")
        if score > meilleur_score:
            meilleur_k, meilleur_score = k, score

    log(f"\nMeilleur nombre de groupes : k={meilleur_k} (silhouette {meilleur_score:.3f})\n")
    modele = KMeans(n_clusters=meilleur_k, n_init=10, random_state=0)
    profils["groupe"] = modele.fit_predict(X)

    log("=== Stations par groupe ===")
    for groupe in sorted(profils["groupe"].unique()):
        membres = profils[profils["groupe"] == groupe]
        log(f"\nGroupe {groupe} ({len(membres)} station(s)) :")
        for _, ligne in membres.iterrows():
            log(f"  - {ligne['nom']}")
        log(f"  Profil moyen : pluie {membres['pluie_annuelle'].mean():.0f} mm/an, "
            f"temp {membres['temperature_moyenne'].mean():.1f}°C, "
            f"humidite {membres['humidite_moyenne'].mean():.0f}%, "
            f"ETo {membres['eto_annuel'].mean():.0f} mm/an, "
            f"vent {membres['vent_moyen'].mean():.1f} km/h")

    return profils


def _annee_campagne(jour):
    return jour.year if jour.month >= 9 else jour.year - 1


def classifier_campagnes(log=print):
    session = SessionLocal()
    stations = session.query(Station).filter_by(actif=True).all()
    station_ids = [s.id for s in stations]

    mesures = (
        session.query(Mesure)
        .filter(Mesure.station_id.in_(station_ids), Mesure.type_donnee == "Mesuré")
        .all()
    )
    session.close()

    df = pd.DataFrame([{"date": m.date_heure.date(), "station_id": m.station_id, "pluie": m.pluie or 0}
                        for m in mesures])
    df["annee_campagne"] = df["date"].apply(_annee_campagne)

    # Cumul reseau : moyenne du cumul de pluie des stations, par campagne (comme le
    # releve de precipitations officiel), pas juste une somme brute toutes stations
    # confondues qui favoriserait les campagnes avec plus de stations actives.
    cumul_par_station_campagne = df.groupby(["annee_campagne", "station_id"])["pluie"].sum()
    cumul_reseau = cumul_par_station_campagne.groupby("annee_campagne").mean()

    # Couverture reseau (nb de jours avec au moins une mesure) par campagne : la toute
    # premiere campagne (donnees ne debutant qu'a mi-2016 pour la plupart des stations)
    # et la campagne en cours (pas encore terminee) sont incompletes et non comparables
    # a une normale annuelle complete - a exclure de la classification, pas juste "EN COURS".
    SEUIL_JOURS_COUVERTS = 300  # sur ~365 jours de campagne
    nb_jours_couverts = df.groupby("annee_campagne")["date"].nunique()

    log(f"Normale annuelle reseau (reprise du bulletin SED) : {NORMALE_ANNUELLE_MM:.0f} mm\n")
    log("=== Classification des campagnes agricoles ===")
    resultats = []
    for annee, cumul in cumul_reseau.items():
        ratio = cumul / NORMALE_ANNUELLE_MM
        jours = nb_jours_couverts.get(annee, 0)
        if jours < SEUIL_JOURS_COUVERTS:
            categorie = f"DONNEES INSUFFISANTES ({jours} jours couverts / ~365)"
        elif ratio < SEUIL_SECHE:
            categorie = "SECHE"
        elif ratio > SEUIL_HUMIDE:
            categorie = "HUMIDE"
        else:
            categorie = "NORMALE"
        resultats.append({"campagne": f"{annee}-{annee+1}", "cumul_mm": round(cumul, 1),
                           "pct_normale": round(100 * ratio, 0), "jours_couverts": jours,
                           "categorie": categorie})
        log(f"  Campagne {annee}-{annee+1} : {cumul:.0f} mm ({100*ratio:.0f}% de la normale, "
            f"{jours} j couverts) -> {categorie}")

    return pd.DataFrame(resultats)


if __name__ == "__main__":
    print("### Regroupement des stations par profil climatique ###\n")
    regrouper_stations()
    print("\n### Classification des campagnes agricoles ###\n")
    classifier_campagnes()
