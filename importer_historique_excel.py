import os
import sys
import glob
import pandas as pd
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


def importer_feuille(df, station, session_db):
    """Importe une feuille (une station) dans la table mesures.

    Ne retouche pas les dates déjà confirmées en base ("Mesuré") : une fois une
    journée mesurée enregistrée, elle ne change plus, inutile de la relire à
    chaque exécution. Seules les dates absentes, ou présentes uniquement en
    "Prévision" (donc pas encore finalisées), sont (ré)écrites."""
    donnees = df.iloc[4:].copy()
    donnees.columns = [
        "col0", "date", "eto", "pluie",
        "temp_min", "temp_moy", "temp_max",
        "hum_min", "hum_moy", "hum_max",
        "rayonnement", "vent", "direction_vent", "type_donnee"
    ]

    types_existants = {
        m.date_heure: m.type_donnee
        for m in session_db.query(Mesure.date_heure, Mesure.type_donnee)
        .filter(Mesure.station_id == station.id)
        .all()
    }

    total_ecrites = 0
    total_ignorees = 0
    for _, ligne in donnees.iterrows():
        if pd.isna(ligne["date"]):
            continue

        date_mesure = pd.to_datetime(ligne["date"], format="%d/%m/%Y", dayfirst=True)

        if types_existants.get(date_mesure) == "Mesuré":
            total_ignorees += 1
            continue

        # Ligne "plate" (température et/ou humidité à 0 partout) : signature de
        # panne capteur, pas une vraie mesure. On ne l'importe jamais, sinon un
        # nettoyage précédent (nettoyer_donnees.py) serait défait au prochain import.
        temp_plate = ligne["temp_min"] == 0 and ligne["temp_moy"] == 0 and ligne["temp_max"] == 0
        hum_plate = ligne["hum_min"] == 0 and ligne["hum_moy"] == 0 and ligne["hum_max"] == 0
        if temp_plate or hum_plate:
            total_ignorees += 1
            continue

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
        total_ecrites += 1

    session_db.commit()
    return total_ecrites, total_ignorees


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

        nb_ecrites, nb_ignorees = importer_feuille(df, station, session_db)
        resultats[station.nom] = (nb_ecrites, nb_ignorees)
        log(f"  [OK] {station.nom} ({nom_feuille}) : {nb_ecrites} écrite(s), "
            f"{nb_ignorees} déjà confirmée(s) ignorée(s).")

    return resultats


def importer_dossier(dossier, log=print):
    """Importe tous les fichiers .xlsx d'un dossier. Ré-exécutable sans risque de doublons
    et sans retraiter les dates déjà confirmées ("Mesuré") en base — seules les dates
    nouvelles ou encore en "Prévision" sont (ré)écrites à chaque exécution."""
    session_db = SessionLocal()
    fichiers = sorted(glob.glob(os.path.join(dossier, "*.xlsx")))
    log(f"{len(fichiers)} fichier(s) Excel trouvé(s) dans {dossier}")

    total_global = {}
    for chemin in fichiers:
        log(f"\nTraitement de {os.path.basename(chemin)}...")
        try:
            resultats = importer_fichier(chemin, session_db, log=log)
            for station_nom, (nb_ecrites, nb_ignorees) in resultats.items():
                ecrites_cumulees, ignorees_cumulees = total_global.get(station_nom, (0, 0))
                total_global[station_nom] = (ecrites_cumulees + nb_ecrites, ignorees_cumulees + nb_ignorees)
        except Exception as e:
            log(f"  [ERREUR] {os.path.basename(chemin)} : {e}")

    session_db.close()

    log("\n=== Résumé ===")
    total_ecrites = total_ignorees = 0
    for station_nom, (nb_ecrites, nb_ignorees) in sorted(total_global.items()):
        log(f"  {station_nom} : {nb_ecrites} écrite(s), {nb_ignorees} ignorée(s)")
        total_ecrites += nb_ecrites
        total_ignorees += nb_ignorees
    log(f"Total : {total_ecrites} mesure(s) écrite(s), {total_ignorees} déjà confirmée(s) ignorée(s).")


if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else "."
    importer_dossier(dossier)
