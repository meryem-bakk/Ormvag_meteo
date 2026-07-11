from sqlalchemy import Column, Integer, String, Float, Boolean
from app.database import Base

class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    actif = Column(Boolean, default=True)
    identifiant_externe = Column(String, nullable=True)
    province = Column(String, nullable=True)