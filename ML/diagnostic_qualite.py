import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

session = SessionLocal()
stations = session.query(Station).filter_by(actif=True).order_by(Station.nom).all()

print(f"{'Station':<32} {'N':>5} {'Debut':>11} {'Fin':>11} {'Trous':>6} {'Dup':>4} "
      f"{'Flat0':>6} {'HR>100':>7} {'HR=0':>5} {'Min>Max':>8} {'Pluie<0':>8} {'Prevision':>9}")

for station in stations:
    mesures = session.query(Mesure).filter(Mesure.station_id == station.id).order_by(Mesure.date_heure).all()
    if not mesures:
        continue

    dates = [m.date_heure.date() for m in mesures]
    n = len(mesures)
    debut, fin = dates[0], dates[-1]

    doublons = n - len(set(dates))

    attendu = dates[0]
    trous = 0
    vus = set()
    for d in dates:
        if d in vus:
            continue
        vus.add(d)
        while attendu < d:
            trous += 1
            attendu += timedelta(days=1)
        attendu = d + timedelta(days=1)

    flat0 = sum(1 for m in mesures if m.temperature == 0 and m.temperature_min == 0 and m.temperature_max == 0)
    hr_sup100 = sum(1 for m in mesures if (m.humidite or 0) > 100 or (m.humidite_max or 0) > 100)
    hr_zero = sum(1 for m in mesures if m.humidite == 0 and m.humidite_min == 0 and m.humidite_max == 0)
    incoherent = sum(
        1 for m in mesures
        if m.temperature_min is not None and m.temperature_max is not None
        and (m.temperature_min > m.temperature_max)
    )
    pluie_neg = sum(1 for m in mesures if (m.pluie or 0) < 0)
    previsions = sum(1 for m in mesures if m.type_donnee == "Prévision")

    print(f"{station.nom:<32} {n:>5} {str(debut):>11} {str(fin):>11} {trous:>6} {doublons:>4} "
          f"{flat0:>6} {hr_sup100:>7} {hr_zero:>5} {incoherent:>8} {pluie_neg:>8} {previsions:>9}")

session.close()
