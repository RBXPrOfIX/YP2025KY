# server/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import DEFAULT_DATABASE_URL
from models import Base
import logging
from typing import Generator

logger = logging.getLogger(__name__)

engine = create_engine(DEFAULT_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Создание таблиц
def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(lyrics)"))
        cols = [row[1] for row in result]
        if 'genre' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN genre TEXT"))
        if 'lyrics_hash' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN lyrics_hash TEXT"))
    logger.info("База данных инициализирована")

# Зависимость FastAPI
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()