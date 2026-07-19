from app.database import SessionLocal
from app.services.premier_demarrage import _creer_roles

session = SessionLocal()
_creer_roles(session, log=print)
session.close()
