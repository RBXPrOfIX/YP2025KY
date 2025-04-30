from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import DEFAULT_DATABASE_URL
from models import Base
import logging
from typing import Generator

logger = logging.getLogger(__name__)

engine = create_engine(DEFAULT_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(lyrics)"))]
        if 'genre' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN genre TEXT"))
        if 'lyrics_hash' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN lyrics_hash TEXT"))
        if 'sbert_embedding' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN sbert_embedding BLOB"))
        if 'deep_emotion_vec' not in cols:
            conn.execute(text("ALTER TABLE lyrics ADD COLUMN deep_emotion_vec BLOB"))
    logger.info("База данных инициализирована и схема проверена")

# Зависимость FastAPI

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()