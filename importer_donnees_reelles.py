import pandas as pd
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


def nettoyer_nom_station(nom_feuille):
    return nom_feuille.replace("_", " ").replace(".", " ").strip()


def importer_fichier(chemin_fichier, log=print):
    xls = pd.ExcelFile(chemin_fichier)
    session = SessionLocal()

    total_lignes_importees = 0

    for nom_feuille in xls.sheet_names:
        if nom_feuille.lower() == "worksheet":
            continue

        df = pd.read_excel(xls, sheet_name=nom_feuille, header=None)
        donnees = df.iloc[4:].copy()
        donnees.columns = [
            "col0", "date", "eto", "pluie",
            "temp_min", "temp_moy", "temp_max",
            "hum_min", "hum_moy", "hum_max",
            "rayonnement", "vent", "direction_vent", "type_donnee"
        ]

        station = session.query(Station).filter_by(identifiant_externe=nom_feuille).first()
        if not station:
            dernier_code = session.query(Station).filter(
                Station.code.like("REAL-%")
            ).order_by(Station.id.desc()).first()
            prochain_numero = 1
            if dernier_code:
                prochain_numero = int(dernier_code.code.split("-")[1]) + 1

            station = Station(
                nom=nettoyer_nom_station(nom_feuille),
                code=f"REAL-{prochain_numero:02d}",
                latitude=0, longitude=0, altitude=0,
                actif=True,
                identifiant_externe=nom_feuille,
            )
            session.add(station)
            session.commit()
            log(f"Nouvelle station créée : {station.nom} ({station.code}).")

        lignes_importees_ici = 0
        for _, ligne in donnees.iterrows():
            if pd.isna(ligne["date"]):
                continue

            date_mesure = pd.to_datetime(ligne["date"], format="%d/%m/%Y", dayfirst=True)

            session.query(Mesure).filter(
                Mesure.station_id == station.id,
                Mesure.date_heure == date_mesure
            ).delete()

            session.add(Mesure(
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
            lignes_importees_ici += 1

        session.commit()
        log(f"{nom_feuille} → {lignes_importees_ici} jour(s) importé(s).")
        total_lignes_importees += lignes_importees_ici

    session.close()
    log(f"Total : {total_lignes_importees} mesure(s) importée(s).")
    return total_lignes_importees