from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Mesure(Base):
    __tablename__ = "mesures"

    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    date_heure = Column(DateTime, nullable=False)

    temperature = Column(Float)       # moyenne
    temperature_min = Column(Float, nullable=True)
    temperature_max = Column(Float, nullable=True)

    humidite = Column(Float)          # moyenne
    humidite_min = Column(Float, nullable=True)
    humidite_max = Column(Float, nullable=True)

    pluie = Column(Float)
    vent = Column(Float)
    direction_vent = Column(String, nullable=True)
    rayonnement = Column(Float, nullable=True)
    eto = Column(Float, nullable=True)

    type_donnee = Column(String, default="Simulé")  # "Mesuré", "Prévision", ou "Simulé"

    station = relationship("Station")