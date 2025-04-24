# server/main.py
from fastapi import FastAPI
from config import logger, GENIUS_TOKEN
from api.endpoints import router as api_router
import lyricsgenius

# Инициализация FastAPI
app = FastAPI(title="Lyrics Semantic API")

# Инициализация Genius
genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True

# Подключение маршрутов
app.include_router(api_router)

logger.info("FastAPI приложение инициализировано")
