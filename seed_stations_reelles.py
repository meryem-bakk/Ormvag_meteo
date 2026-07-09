from app.database import SessionLocal
from app.models.station import Station

# (identifiant_externe exact du site, nom affiché, longitude, latitude)
stations_reelles = [
    ("Pce_Kenitra_S.Larbaa", "Souk Larbaa (Kénitra)", -6.00067, 34.67090),
    ("Pce_S.Sliman_S.sliman", "Sidi Slimane", -5.93738, 34.25191),
    ("Pce_Kenitra_S.Allal-Tazi", "Sidi Allal Tazi (Kénitra)", -6.33066, 34.51860),
    ("PCE_KENITRA_NORD3", "Kénitra Nord 3", -6.06312, 34.66965),
    ("Pce_S.Kacem_Zeggoutta", "Zeggoutta (Sidi Kacem)", -5.53122, 34.16882),
    ("PCE_KENITRA_OUED ETTINE", "Oued Ettine (Kénitra)", -5.71564, 34.69691),
    ("METEO KHENICHET", "Khénichet", -5.68279, 34.42399),
    ("Pce_Kenitra_Souk-Tlat", "Souk Tlat (Kénitra)", -6.15635, 34.62290),
    ("Pce_S.Kacem_BELKSIRI", "Mechraa Bel Ksiri (Sidi Kacem)", -5.95139, 34.57700),
    ("Pce_Kenitra_Lamnassra", "Lamnassra (Kénitra)", -6.48486, 34.45630),
    ("KENITRA-BANLIEUE", "Kénitra Banlieue", -6.44178, 34.33617),
    ("Pce_S.Kacem_S.Kacem", "Sidi Kacem", -5.79713, 34.25410),
    ("AMEUR CHAMALIA-DAR GUEDDARI", "Ameur Chamalia - Dar Gueddari", -6.12745, 34.42843),
    ("SIDIYAHYA_ELGHARB", "Sidi Yahya El Gharb", -6.16150, 34.23947),
]

session = SessionLocal()

nb_crees = 0
nb_mis_a_jour = 0

for i, (identifiant, nom, longitude, latitude) in enumerate(stations_reelles, start=1):
    station = session.query(Station).filter_by(identifiant_externe=identifiant).first()

    if station:
        station.nom = nom
        station.latitude = latitude
        station.longitude = longitude
        nb_mis_a_jour += 1
    else:
        # Génère un code unique REAL-XX qui n'existe pas encore
        code = f"REAL-{i:02d}"
        while session.query(Station).filter_by(code=code).first():
            i += 1
            code = f"REAL-{i:02d}"

        session.add(Station(
            nom=nom,
            code=code,
            latitude=latitude,
            longitude=longitude,
            altitude=0,
            actif=True,
            identifiant_externe=identifiant,
        ))
        nb_crees += 1

session.commit()
session.close()

print(f"{nb_crees} station(s) créée(s), {nb_mis_a_jour} mise(s) à jour.")