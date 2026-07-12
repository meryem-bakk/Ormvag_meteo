import os
import sys
import glob
import pandas as pd
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


def importer_feuille(df, station, session_db):
    """Importe une feuille (une station) dans la table mesures.
    Remplace les mesures existantes à la même date (idempotent, ré-exécutable sans doublons)."""
    donnees = df.iloc[4:].copy()
    donnees.columns = [
        "col0", "date", "eto", "pluie",
        "temp_min", "temp_moy", "temp_max",
        "hum_min", "hum_moy", "hum_max",
        "rayonnement", "vent", "direction_vent", "type_donnee"
    ]

    total = 0
    for _, ligne in donnees.iterrows():
        if pd.isna(ligne["date"]):
            continue

        date_mesure = pd.to_datetime(ligne["date"], format="%d/%m/%Y", dayfirst=True)

        session_db.query(Mesure).filter(
            Mesure.station_id == station.id,
            Mesure.date_heure == date_mesure
        ).delete()

        session_db.add(Mesure(
            station_id=station.id,
            date_heure=date_mesure,
            eto=float(ligne["eto"]) if pd.notna(ligne["eto"]) else None,
            pluie=float(ligne["pluie"]) if pd.notna(ligne["pluie"]) else None,
            temperature_min=float(ligne["temp_min"]) if pd.notna(ligne["temp_min"]) else None,
            temperature=float(ligne["temp_moy"]) if pd.notna(ligne["temp_moy"]) else None,
            temperature_max=float(ligne["temp_max"]) if pd.notna(ligne["temp_max"]) else None,
            humidite_min=float(ligne["hum_min"]) if pd.notna(ligne["hum_min"]) else None,
            humidite=float(ligne["hum_moy"]) if pd.notna(ligne["hum_moy"]) else None,
            humidite_max=float(ligne["hum_max"]) if pd.notna(ligne["hum_max"]) else None,
            rayonnement=float(ligne["rayonnement"]) if pd.notna(ligne["rayonnement"]) else None,
            vent=float(ligne["vent"]) if pd.notna(ligne["vent"]) else None,
            direction_vent=str(ligne["direction_vent"]) if pd.notna(ligne["direction_vent"]) else None,
            type_donnee=str(ligne["type_donnee"]) if pd.notna(ligne["type_donnee"]) else "Mesuré",
        ))
        total += 1

    session_db.commit()
    return total


def importer_fichier(chemin, session_db, log=print):
    """Importe un fichier Excel : chaque feuille est associée à une station via son nom
    (qui doit correspondre à l'identifiant_externe de la station en base). Un même fichier
    peut donc contenir l'historique de plusieurs stations (plusieurs feuilles)."""
    xls = pd.ExcelFile(chemin)
    resultats = {}

    for nom_feuille in xls.sheet_names:
        if nom_feuille.lower() == "worksheet":
            continue

        df = pd.read_excel(xls, sheet_name=nom_feuille, header=None)
        if len(df) < 5:
            continue

        # Le nom de l'onglet peut être soit l'identifiant_externe (ex. "Pce_Kenitra_S.Larbaa"),
        # soit directement le nom affiché de la station (ex. "Souk Larbaa (Kénitra)").
        station = (
            session_db.query(Station).filter_by(identifiant_externe=nom_feuille).first()
            or session_db.query(Station).filter_by(nom=nom_feuille).first()
        )
        if not station:
            log(f"  [IGNORÉ] Feuille '{nom_feuille}' : aucune station correspondante (ni identifiant_externe, ni nom) en base.")
            continue

        nb = importer_feuille(df, station, session_db)
        resultats[station.nom] = nb
        log(f"  [OK] {station.nom} ({nom_feuille}) : {nb} mesure(s) importée(s)/mise(s) à jour.")

    return resultats


def importer_dossier(dossier, log=print):
    """Importe tous les fichiers .xlsx d'un dossier. Ré-exécutable sans risque de doublons
    (chaque mesure remplace l'éventuelle mesure existante à la même date pour la même station)."""
    session_db = SessionLocal()
    fichiers = sorted(glob.glob(os.path.join(dossier, "*.xlsx")))
    log(f"{len(fichiers)} fichier(s) Excel trouvé(s) dans {dossier}")

    total_global = {}
    for chemin in fichiers:
        log(f"\nTraitement de {os.path.basename(chemin)}...")
        try:
            resultats = importer_fichier(chemin, session_db, log=log)
            for station_nom, nb in resultats.items():
                total_global[station_nom] = total_global.get(station_nom, 0) + nb
        except Exception as e:
            log(f"  [ERREUR] {os.path.basename(chemin)} : {e}")

    session_db.close()

    log("\n=== Résumé ===")
    for station_nom, nb in sorted(total_global.items()):
        log(f"  {station_nom} : {nb} mesure(s)")
    log(f"Total : {sum(total_global.values())} mesure(s) importée(s)/mise(s) à jour.")


if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else "."
    importer_dossier(dossier)
