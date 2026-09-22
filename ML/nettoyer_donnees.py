import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


def trouver_lignes_plates(session):
    """Retourne les mesures où température ET/OU humidité sont à 0 sur min/moy/max
    simultanément — signe caractéristique d'une panne capteur, pas une vraie mesure."""
    return session.query(Mesure).filter(
        ((Mesure.temperature == 0) & (Mesure.temperature_min == 0) & (Mesure.temperature_max == 0))
        | ((Mesure.humidite == 0) & (Mesure.humidite_min == 0) & (Mesure.humidite_max == 0))
    ).all()


def nettoyer(dry_run=True, log=print):
    session = SessionLocal()
    lignes = trouver_lignes_plates(session)

    par_station = {}
    for m in lignes:
        par_station.setdefault(m.station_id, []).append(m)

    stations = {s.id: s.nom for s in session.query(Station).all()}

    log(f"{'Suppression' if not dry_run else 'Simulation (dry-run)'} — {len(lignes)} ligne(s) suspecte(s) au total\n")
    for station_id, ms in sorted(par_station.items(), key=lambda kv: stations.get(kv[0], "")):
        log(f"  {stations.get(station_id, station_id)} : {len(ms)} ligne(s)")

    if not dry_run:
        for m in lignes:
            session.delete(m)
        session.commit()
        log("\nSuppression effectuée.")
    else:
        log("\nAucune suppression effectuée (dry-run). Relancer avec dry_run=False pour appliquer.")

    session.close()
    return len(lignes)


if __name__ == "__main__":
    applique = "--appliquer" in sys.argv
    nettoyer(dry_run=not applique)
