from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class HistoriqueModification(Base):
    __tablename__ = "historique_modifications"

    id = Column(Integer, primary_key=True)
    acteur_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)          # ex: "Création", "Modification", "Suppression"
    cible_type = Column(String, nullable=False)       # ex: "Utilisateur", "Rôle"
    cible_id = Column(Integer, nullable=True)
    description = Column(String, nullable=False)
    date_heure = Column(DateTime, server_default=func.now())

    acteur = relationship("User", foreign_keys=[acteur_id])
