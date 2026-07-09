from sqlalchemy import Column, Integer, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class IndicateurJournalier(Base):
    __tablename__ = "indicateurs_journaliers"

    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    date = Column(Date, nullable=False)

    cumul_pluie_7j = Column(Float)
    cumul_pluie_30j = Column(Float)
    cumul_pluie_saison = Column(Float)
    cumul_eto_7j = Column(Float)
    bilan_hydrique_7j = Column(Float)  # cumul_pluie_7j - cumul_eto_7j
    jours_sans_pluie = Column(Integer)
    gel_detecte = Column(Boolean, default=False)       # temp_min < 0°C
    stress_thermique = Column(Boolean, default=False)  # temp_max > 38°C
    gdd_jour = Column(Float)            # degrés-jours de croissance (base 10°C)
    gdd_cumule_saison = Column(Float)

    station = relationship("Station")