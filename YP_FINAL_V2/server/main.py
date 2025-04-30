import asyncio

from fastapi import FastAPI
from config import logger, GENIUS_TOKEN
import lyricsgenius

from database import init_db
from services.faiss_index import faiss_service
from services.idf_cache import idf_service
from api.endpoints import router as api_router

# 1) Инициализация БД и схемы
init_db()

# 2) Построение FAISS-индекса
faiss_service.build_index()

# 3) Первичный расчёт IDF-кеша
idf_service.refresh()

app = FastAPI(title="Lyrics Semantic API")

genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True

def start_periodic_tasks():
    async def refresh_idf():
        while True:
            await asyncio.sleep(3600)  # каждый час
            idf_service.refresh()
            logger.info("Periodic IDF cache refresh complete")
    asyncio.create_task(refresh_idf())

@app.on_event("startup")
async def startup_tasks():
    start_periodic_tasks()
    logger.info("FastAPI startup complete, background tasks running")

app.include_router(api_router)
logger.info("FastAPI приложение инициализировано, FAISS-индекс и IDF-кеш готовы")
