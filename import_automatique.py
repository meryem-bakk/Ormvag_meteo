import os
import io
import time
import json
import base64
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

load_dotenv()

URL_LOGIN = "https://avertissement.yobeen.com/user/login"
URL_EXPORT_PAGE = "https://avertissement.yobeen.com/telechargement/excel"
URL_EXPORT = "https://avertissement.yobeen.com/telechargement/downloadexcelSheets"

TELEPHONE = os.getenv("ORMVAG_TELEPHONE")
MOT_DE_PASSE = os.getenv("ORMVAG_MOTDEPASSE")

IDS_SITE = {
    "Pce_Kenitra_S.Larbaa": 16,
    "Pce_S.Sliman_S.sliman": 17,
    "Pce_Kenitra_S.Allal-Tazi": 11,
    "PCE_KENITRA_NORD3": 20,
    "Pce_S.Kacem_Zeggoutta": 35,
    "PCE_KENITRA_OUED ETTINE": 34,
    "METEO KHENICHET": 56,
    "Pce_Kenitra_Souk-Tlat": 12,
    "Pce_S.Kacem_BELKSIRI": 15,
    "Pce_Kenitra_Lamnassra": 14,
    "KENITRA-BANLIEUE": 63,
    "Pce_S.Kacem_S.Kacem": 13,
    "AMEUR CHAMALIA-DAR GUEDDARI": 64,
    "SIDIYAHYA_ELGHARB": 71,
}


def se_connecter(log=print):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    })

    reponse = session.post(URL_LOGIN, data={
        "email": TELEPHONE,
        "password": MOT_DE_PASSE,
    }, allow_redirects=True)

    if "login" in reponse.url.lower():
        raise RuntimeError("Connexion échouée : identifiants invalides ou site injoignable.")

    log("Connexion au site ORMVAG réussie.")
    return session


def telecharger_donnees(session, id_station, date_debut, date_fin):
    session.get(URL_EXPORT_PAGE)

    reponse = session.post(
        URL_EXPORT,
        data={
            "stations[]": id_station,
            "type_data": 2,
            "date_start": date_debut,
            "date_end": date_fin,
        },
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": URL_EXPORT_PAGE,
        }
    )

    if reponse.status_code != 200:
        raise RuntimeError(f"Statut HTTP {reponse.status_code}")

    donnees_json = reponse.json()
    if donnees_json.get("op") != "ok":
        raise RuntimeError(f"Réponse serveur inattendue : {donnees_json}")

    data_url = donnees_json["file"]
    partie_base64 = data_url.split(",", 1)[1]
    contenu_fichier = base64.b64decode(partie_base64)

    return io.BytesIO(contenu_fichier)


def importer_fichier_en_memoire(fichier_bytes, identifiant_externe, session_db):
    xls = pd.ExcelFile(fichier_bytes)
    total = 0

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

        station = session_db.query(Station).filter_by(identifiant_externe=identifiant_externe).first()
        if not station:
            continue

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


def lancer_import_complet(jours_a_recuperer=7, log=print):
    if not TELEPHONE or not MOT_DE_PASSE:
        log("ERREUR : ORMVAG_TELEPHONE ou ORMVAG_MOTDEPASSE manquant dans .env")
        return 0, []

    date_fin = datetime.now().strftime("%Y-%m-%d")
    date_debut = (datetime.now() - timedelta(days=jours_a_recuperer)).strftime("%Y-%m-%d")

    session_web = se_connecter(log=log)
    session_db = SessionLocal()

    total_general = 0
    erreurs = []

    for identifiant_externe, id_site in IDS_SITE.items():
        log(f"Import : {identifiant_externe}...")
        try:
            fichier = telecharger_donnees(session_web, id_site, date_debut, date_fin)
            nb = importer_fichier_en_memoire(fichier, identifiant_externe, session_db)
            log(f"  → {nb} mesure(s) importée(s).")
            total_general += nb
        except Exception as e:
            log(f"  ✗ Erreur : {e}")
            erreurs.append((identifiant_externe, str(e)))

        time.sleep(3)

    session_db.close()
    log(f"=== Terminé : {total_general} mesure(s) au total, {len(erreurs)} erreur(s) ===")
    return total_general, erreurs