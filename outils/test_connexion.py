import os
import sys
# Outil deplace sous outils/ (racine du depot = deux niveaux au-dessus) : sans ce
# chemin explicite, "from app..." echoue quand ce script est lance directement
# (python outils/test_connexion.py), Python resolvant les imports depuis le dossier
# du script et non depuis le dossier courant.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import engine, Base
from app.models.station import Station
from app.models.role import Role
from app.models.user import User

Base.metadata.create_all(engine)
print("Connexion réussie, tables créées.")