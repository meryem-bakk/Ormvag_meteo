from app.database import SessionLocal
from app.services.premier_demarrage import _creer_stations

session = SessionLocal()
_creer_stations(session, log=print)
session.close()
