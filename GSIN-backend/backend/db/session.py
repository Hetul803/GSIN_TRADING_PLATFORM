# backend/db/session.py
from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
from pathlib import Path
from dotenv import dotenv_values

# Try to load from config/.env first, then fall back to environment variable
# Go up from backend/db/session.py -> backend/db -> backend -> GSIN-backend -> gsin_new_git (repo root)
# Priority: 1) Repo root config/.env, 2) Environment variable, 3) SQLite fallback
CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
cfg = {}
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Validate that we got a real DATABASE_URL, not placeholder
    db_url_from_file = cfg.get("DATABASE_URL", "")
    if db_url_from_file and ("user:password@host:port" in db_url_from_file or db_url_from_file.count(":") < 3):
        # Invalid placeholder, ignore this file
        cfg = {}

DATABASE_URL = os.environ.get("DATABASE_URL") or cfg.get("DATABASE_URL", "sqlite:///gsin.db")

# For PostgreSQL, use pool_pre_ping to handle connection issues
connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    connect_args = {"connect_timeout": 10}
elif DATABASE_URL.startswith("sqlite"):
    # SQLite-specific settings
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections before using
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

