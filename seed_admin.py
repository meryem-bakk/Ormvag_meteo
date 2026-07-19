from app.database import SessionLocal
from app.services.premier_demarrage import _creer_roles, _creer_admin

session = SessionLocal()
_creer_roles(session, log=lambda m: None)  # s'assure que le rôle Administrateur existe
_creer_admin(session, log=print)
session.close()
