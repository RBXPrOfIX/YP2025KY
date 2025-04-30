import json
import math
from collections import Counter
from database import SessionLocal
from models import Lyrics
from sqlalchemy import event

class IDFCache:
    def __init__(self):
        self.theme_idf: dict[str, float] = {}
        self.genre_idf: dict[str, float] = {}

    def refresh(self):
        db = SessionLocal()
        try:
            total_docs = db.query(Lyrics).count()
            if total_docs == 0:
                return

            theme_counter: Counter[str] = Counter()
            genre_counter: Counter[str] = Counter()

            # Собираем статистику тем
            for row, in db.query(Lyrics.themes).all():
                items = []
                # поддержка JSON-типа (list) и старых строковых колонок
                if isinstance(row, (list, tuple)):
                    items = row
                elif isinstance(row, str):
                    try:
                        items = json.loads(row)
                    except json.JSONDecodeError:
                        items = []
                for t in set(items):
                    theme_counter[t] += 1

            # Собираем статистику жанров
            for row, in db.query(Lyrics.genre).all():
                items = []
                if isinstance(row, (list, tuple)):
                    items = row
                elif isinstance(row, str):
                    try:
                        items = json.loads(row)
                    except json.JSONDecodeError:
                        items = []
                for g in set(items):
                    genre_counter[g] += 1

            # Вычисляем IDF
            self.theme_idf = {
                t: math.log((total_docs + 1) / (cnt + 1))
                for t, cnt in theme_counter.items()
            }
            self.genre_idf = {
                g: math.log((total_docs + 1) / (cnt + 1))
                for g, cnt in genre_counter.items()
            }
        finally:
            db.close()

idf_service = IDFCache()

# Автоматический refresh TF-IDF после вставки или обновления Lyrics
@event.listens_for(Lyrics, 'after_insert')
@event.listens_for(Lyrics, 'after_update')
def _refresh_idf(mapper, connection, target):
    idf_service.refresh()
