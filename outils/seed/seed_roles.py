import os
import sys
# Outil deplace sous outils/seed/ (racine du depot = trois niveaux au-dessus) : sans ce
# chemin explicite, "from app..." echoue quand ce script est lance directement, Python
# resolvant les imports depuis le dossier du script et non depuis le dossier courant.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.database import SessionLocal
from app.services.premier_demarrage import _creer_roles

session = SessionLocal()
_creer_roles(session, log=print)
session.close()
