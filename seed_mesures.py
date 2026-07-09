import random
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

session = SessionLocal()

stations = session.query(Station).filter_by(actif=True).all()

if not stations:
    print("Aucune station en base. Lance d'abord seed_stations.py.")
    session.close()
    exit()

# Supprime les anciennes mesures simulées pour éviter les doublons si on relance le script
session.query(Mesure).delete()
session.commit()

maintenant = datetime.now().replace(minute=0, second=0, microsecond=0)
debut = maintenant - timedelta(days=7)

nb_mesures = 0
heure_courante = debut

while heure_courante <= maintenant:
    heure_du_jour = heure_courante.hour

    # Cycle jour/nuit réaliste : plus chaud l'après-midi, plus frais la nuit
    if 6 <= heure_du_jour <= 18:
        temp_base = 24 + 10 * abs(12 - heure_du_jour) / 6 * -1 + 10
    else:
        temp_base = 18

    for station in stations:
        # Variation aléatoire légère par station et par heure
        temperature = round(temp_base + random.uniform(-2, 2) + (station.altitude / 200), 1)
        humidite = round(max(30, min(95, 70 - (temperature - 20) * 1.5 + random.uniform(-5, 5))), 1)
        pluie = round(random.choice([0, 0, 0, 0, 0, 0.2, 0.5, 1.2]) if random.random() < 0.08 else 0, 1)
        vent = round(max(0, random.gauss(12, 5)), 1)
        rayonnement = round(max(0, 600 * max(0, 1 - abs(13 - heure_du_jour) / 7)) + random.uniform(-30, 30), 0) if 6 <= heure_du_jour <= 19 else 0
        eto = round(max(0, (temperature - 15) * 0.05 + random.uniform(0, 0.1)), 2)

        session.add(Mesure(
            station_id=station.id,
            date_heure=heure_courante,
            temperature=temperature,
            humidite=humidite,
            pluie=pluie,
            vent=vent,
            rayonnement=rayonnement,
            eto=eto,
        ))
        nb_mesures += 1

    heure_courante += timedelta(hours=1)

session.commit()
session.close()

print(f"{nb_mesures} mesures simulées créées pour {len(stations)} stations sur 7 jours.")