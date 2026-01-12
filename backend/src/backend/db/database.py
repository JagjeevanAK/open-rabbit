from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

DB_URL = os.environ.get("DB_URL") or os.environ.get("DATABASE_URL") or ""

# Use SQLite for testing if no DB_URL is set
if not DB_URL:
    DB_URL = "sqlite:///./test.db"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()