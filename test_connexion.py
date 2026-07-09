from app.database import engine, Base
from app.models.station import Station
from app.models.role import Role
from app.models.user import User

Base.metadata.create_all(engine)
print("Connexion réussie, tables créées.")