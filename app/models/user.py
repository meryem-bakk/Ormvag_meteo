from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    nom_complet = Column(String, nullable=True)
    email = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    actif = Column(Boolean, default=True)
    derniere_connexion = Column(DateTime, nullable=True)
    role = relationship("Role", back_populates="users")