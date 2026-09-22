import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"client_encoding": "utf8"}
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()