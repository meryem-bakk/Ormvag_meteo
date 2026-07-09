from app.database import SessionLocal
from app.models.role import Role

roles_a_creer = [
    ("Administrateur", "Accès complet à toutes les fonctionnalités"),
    ("Technicien", "Gestion des stations, import et consultation des données"),
    ("Consultation", "Lecture seule des données et rapports"),
]

session = SessionLocal()

nb_ajoutes = 0
for nom, description in roles_a_creer:
    if not session.query(Role).filter_by(nom=nom).first():
        session.add(Role(nom=nom, description=description))
        nb_ajoutes += 1

session.commit()
session.close()

print(f"{nb_ajoutes} rôle(s) ajouté(s).")