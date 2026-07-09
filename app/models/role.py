from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True, nullable=False)  # ex: "Administrateur", "Technicien", "Consultation"
    description = Column(String, nullable=True)

    users = relationship("User", back_populates="role")