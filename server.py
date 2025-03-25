from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import httpx
import logging
import logging.config
from pydantic import BaseModel
import threading
import uvicorn
from tkinter import Tk, Button, Label, StringVar, messagebox, Entry, Frame
import asyncio
from datetime import datetime

# --- Конфигурация ---
DEFAULT_DATABASE_URL = "sqlite:///./database.db"
DEFAULT_PORT = 8000
API_TIMEOUT = 10.0

LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": "server.log",
            "formatter": "default",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO",
    },
}

# --- Инициализация логгера ---
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# --- Модели данных (с индексами) ---
Base = declarative_base()

class Lyrics(Base):
    __tablename__ = "lyrics"
    id = Column(Integer, primary_key=True)
    track_name = Column(String(200), index=True)  # Добавлен индекс
    artist = Column(String(200), index=True)      # Добавлен индекс
    lyrics = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(15))
    operation = Column(String(50))
    status = Column(String(20))
    device_info = Column(Text)

# --- Инициализация БД с пулом соединений ---
engine = create_engine(
    DEFAULT_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,         # Размер пула
    max_overflow=20       # Максимальное количество переполнений
)

# Создаем таблицы
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FastAPI приложение ---
app = FastAPI()

# --- Вспомогательные функции ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def fetch_lyrics(track_name: str, artist: str) -> str:
    url = f"https://api.lyrics.ovh/v1/{artist}/{track_name}"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(url)
            return response.json().get("lyrics", "Текст не найден") if response.status_code == 200 else "Ошибка API"
    except Exception as e:
        logger.error(f"Ошибка внешнего API: {str(e)}")
        return "Сервис недоступен"

# --- API Endpoints ---
@app.get("/get_lyrics")
async def get_lyrics(request: Request, track_name: str, artist: str, db: Session = Depends(get_db)):
    try:
        db_lyrics = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()
        
        if not db_lyrics:
            lyrics = await fetch_lyrics(track_name, artist)
            db.add(Lyrics(track_name=track_name, artist=artist, lyrics=lyrics))
            db.commit()
            db_lyrics = db.query(Lyrics).filter_by(track_name=track_name, artist=artist).first()

        db.add(Log(
            ip_address=request.client.host,
            operation="get_lyrics",
            status="success",
            device_info=request.headers.get("User-Agent", "Неизвестно")
        ))
        db.commit()
        
        return {"track": track_name, "artist": artist, "lyrics": db_lyrics.lyrics}

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/find_similar")
async def find_similar(db: Session = Depends(get_db)):
    try:
        # Возвращаем 5 случайных треков
        random_tracks = db.query(Lyrics).order_by(func.random()).limit(5).all()
        return {
            "similar_tracks": [
                {"track": t.track_name, "artist": t.artist} 
                for t in random_tracks
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка поиска похожих треков: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка обработки")

# --- GUI для управления сервером ---
class ServerGUI:
    def __init__(self):
        self.server_thread = None
        self.root = Tk()
        self.root.title("Server Control Panel")
        
        # Поля ввода
        self.config_frame = Frame(self.root)
        self.config_frame.pack(pady=10)
        
        Label(self.config_frame, text="Порт:").grid(row=0, column=0)
        self.port_entry = Entry(self.config_frame)
        self.port_entry.insert(0, str(DEFAULT_PORT))
        self.port_entry.grid(row=0, column=1)
        
        Label(self.config_frame, text="Путь к БД:").grid(row=1, column=0)
        self.db_entry = Entry(self.config_frame)
        self.db_entry.insert(0, DEFAULT_DATABASE_URL)
        self.db_entry.grid(row=1, column=1)
        
        # Статус и кнопки
        self.status_var = StringVar(value="Server: STOPPED")
        Label(self.root, textvariable=self.status_var).pack(pady=10)
        
        Button(self.root, text="Start Server", command=self.start_server).pack(pady=5)
        Button(self.root, text="Stop Server", command=self.stop_server).pack(pady=5)
        Button(self.root, text="Exit", command=self.root.quit).pack(pady=5)

    def start_server(self):
        if not self.server_thread or not self.server_thread.is_alive():
            global engine, SessionLocal
            DATABASE_URL = self.db_entry.get()
            PORT = int(self.port_entry.get())
            
            engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(
                    app, 
                    host="0.0.0.0", 
                    port=PORT,
                    log_config=LOGGING_CONFIG
                ),
                daemon=True
            )
            self.server_thread.start()
            self.status_var.set("Server: RUNNING")
            messagebox.showinfo("Info", f"Сервер запущен на порту {PORT}")

    def stop_server(self):
        if self.server_thread and self.server_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.shutdown_server(), loop=asyncio.new_event_loop())
            self.status_var.set("Server: STOPPED")
            messagebox.showinfo("Info", "Сервер остановлен")
    
    @staticmethod
    async def shutdown_server():
        await uvicorn.Server(uvicorn.Config(app)).shutdown()
    
    def run(self):
        self.root.mainloop()

# --- Инициализация БД ---
engine = create_engine(DEFAULT_DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if __name__ == "__main__":
    gui = ServerGUI()
    gui.run()