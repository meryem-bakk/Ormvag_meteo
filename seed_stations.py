from app.database import SessionLocal
from app.models.station import Station

# Stations fictives réparties dans le périmètre du Gharb (région de Kénitra, Maroc)
stations_simulees = [
    ("Station Sidi Allal", "S01", 34.1522, -6.5401, 12),
    ("Station Mechraa Bel Ksiri", "S02", 34.1105, -5.9512, 48),
    ("Station Souk El Arbaa", "S03", 34.6833, -5.9833, 20),
    ("Station Had Kourt", "S04", 34.6167, -5.9333, 25),
    ("Station Sidi Slimane", "S05", 34.2650, -5.9250, 66),
    ("Station Sidi Kacem", "S06", 34.2250, -5.7083, 130),
    ("Station Kénitra Centre", "S07", 34.2610, -6.5802, 15),
    ("Station Mnasra", "S08", 34.3667, -6.4167, 8),
    ("Station Lalla Mimouna", "S09", 34.8667, -6.0500, 40),
    ("Station Dar Bel Amri", "S10", 34.4667, -5.9833, 55),
    ("Station Jorf El Melha", "S11", 34.3833, -5.8667, 60),
    ("Station Sidi Yahya El Gharb", "S12", 34.3025, -6.2969, 30),
    ("Station Arbaoua", "S13", 34.7167, -6.0167, 45),
    ("Station Ouazzane", "S14", 34.7970, -5.6010, 420),
    ("Station Souk Tlet", "S15", 34.4500, -6.2667, 35),
    ("Station Had Soualem Gharb", "S16", 34.3271, -6.7460, 18),
    ("Station Moulay Bousselham", "S17", 34.8833, -6.2833, 5),
]

session = SessionLocal()

nb_ajoutees = 0
for nom, code, lat, lon, alt in stations_simulees:
    existe_deja = session.query(Station).filter_by(code=code).first()
    if not existe_deja:
        session.add(Station(
            nom=nom, code=code,
            latitude=lat, longitude=lon, altitude=alt,
            actif=True
        ))
        nb_ajoutees += 1

session.commit()
session.close()

print(f"{nb_ajoutees} stations ajoutées (sur {len(stations_simulees)} au total).")