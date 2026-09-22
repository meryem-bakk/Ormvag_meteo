"""Correlation entre stations du reseau ORMVAG, en complement de la typologie
par profil climatique (typologie_stations_saisons.py) : deux stations au meme
profil moyen peuvent tout de meme varier de facon tres differente jour a jour
(ex. pluie convective tres locale). Utile pour identifier les stations
redondantes (maintenance/investissement) et les paires potentiellement utiles
en cas de panne capteur (imputation par la station la plus correlee).

Script d'analyse ponctuelle (pas d'integration a l'app), a relancer
manuellement si besoin d'une analyse a jour.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

DOSSIER_SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultats_correlation")


def _series_journalieres(session):
    """Une colonne par station, une ligne par jour : pluie et temperature moyenne,
    a partir des seules mesures confirmees ("Mesure")."""
    stations = session.query(Station).filter_by(actif=True).order_by(Station.id).all()
    noms = {s.id: s.nom for s in stations}

    mesures = (
        session.query(Mesure)
        .filter(Mesure.station_id.in_(noms.keys()), Mesure.type_donnee == "Mesuré")
        .all()
    )
    df = pd.DataFrame([{
        "date": m.date_heure.date(), "station": noms[m.station_id],
        "pluie": m.pluie, "temperature": m.temperature,
    } for m in mesures])

    pluie = df.pivot_table(index="date", columns="station", values="pluie", aggfunc="sum")
    temperature = df.pivot_table(index="date", columns="station", values="temperature", aggfunc="mean")
    return pluie, temperature


def _paires_extremes(matrice_corr, log):
    """Liste les paires de stations les plus et les moins correlees (hors diagonale)."""
    paires = []
    stations = matrice_corr.columns.tolist()
    for i, a in enumerate(stations):
        for b in stations[i + 1:]:
            valeur = matrice_corr.loc[a, b]
            if pd.notna(valeur):
                paires.append((a, b, valeur))
    paires.sort(key=lambda p: p[2])

    log("  5 paires les MOINS correlees :")
    for a, b, v in paires[:5]:
        log(f"    {a} <-> {b} : r = {v:.2f}")
    log("  5 paires les PLUS correlees :")
    for a, b, v in paires[-5:][::-1]:
        log(f"    {a} <-> {b} : r = {v:.2f}")
    return paires


def _heatmap(matrice_corr, titre, chemin_sortie):
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(matrice_corr.values, vmin=-1, vmax=1, cmap="RdYlBu_r")
    ax.set_xticks(range(len(matrice_corr.columns)))
    ax.set_yticks(range(len(matrice_corr.columns)))
    ax.set_xticklabels(matrice_corr.columns, rotation=90, fontsize=8)
    ax.set_yticklabels(matrice_corr.columns, fontsize=8)
    ax.set_title(titre, fontsize=12)
    fig.colorbar(im, ax=ax, label="Coefficient de corrélation (Pearson)")
    fig.tight_layout()
    fig.savefig(chemin_sortie, dpi=150)
    plt.close(fig)


def analyser_correlations(log=print):
    session = SessionLocal()
    pluie, temperature = _series_journalieres(session)
    session.close()

    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    resultats = {}
    for nom_variable, df in [("pluie", pluie), ("temperature", temperature)]:
        log(f"\n=== Corrélation entre stations - {nom_variable} (jours communs uniquement) ===")
        matrice = df.corr(method="pearson", min_periods=30)
        moyenne_hors_diag = matrice.values[~np.eye(len(matrice), dtype=bool)]
        moyenne_hors_diag = moyenne_hors_diag[~np.isnan(moyenne_hors_diag)]
        log(f"  Corrélation moyenne inter-stations : r = {moyenne_hors_diag.mean():.2f} "
            f"(min {moyenne_hors_diag.min():.2f}, max {moyenne_hors_diag.max():.2f})")
        _paires_extremes(matrice, log)

        chemin = os.path.join(DOSSIER_SORTIE, f"correlation_{nom_variable}.png")
        _heatmap(matrice, f"Corrélation entre stations — {nom_variable}", chemin)
        log(f"  Heatmap enregistrée : {chemin}")
        resultats[nom_variable] = matrice

    return resultats


if __name__ == "__main__":
    print("### Corrélation entre stations du réseau ORMVAG ###")
    analyser_correlations()
