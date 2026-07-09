import bcrypt
from app.database import SessionLocal
from app.models.role import Role
from app.models.user import User

session = SessionLocal()

role_admin = session.query(Role).filter_by(nom="Administrateur").first()
if not role_admin:
    role_admin = Role(nom="Administrateur", description="Accès complet")
    session.add(role_admin)
    session.commit()

utilisateur_existant = session.query(User).filter_by(username="admin").first()
if not utilisateur_existant:
    nouvel_admin = User(
        username="admin",
        password_hash=bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        nom_complet="Administrateur",
        role_id=role_admin.id,
        actif=True
    )
    session.add(nouvel_admin)
    session.commit()
    print("Utilisateur admin créé (identifiant: admin / mot de passe: admin123)")
else:
    print("L'utilisateur admin existe déjà.")

session.close()