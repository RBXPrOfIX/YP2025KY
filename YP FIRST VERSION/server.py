# server.py
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import lyricsgenius
import logging
import logging.config
import threading
import uvicorn
import asyncio
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QStatusBar, QMessageBox)
from PyQt5.QtCore import Qt, QObject, pyqtSignal

# --- Конфигурация ---
DEFAULT_DATABASE_URL = "sqlite:///./database.db"
DEFAULT_PORT = 8000
GENIUS_TOKEN = "OheKD5f6K0vm_3aKWGfb5wE8Et4bkt_TTzXRVWcRr1Ywlb8VU1yMxVC6dATKMiw7"

# --- Инициализация Genius ---
genius = lyricsgenius.Genius(GENIUS_TOKEN)
genius.verbose = False
genius.remove_section_headers = True

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

# --- Модели данных ---
Base = declarative_base()

class Lyrics(Base):
    __tablename__ = "lyrics"
    id = Column(Integer, primary_key=True)
    track_name = Column(String(200), index=True)
    artist = Column(String(200), index=True)
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

# --- Инициализация БД ---
engine = create_engine(
    DEFAULT_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20
)
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
    try:
        song = genius.search_song(track_name, artist)
        return song.lyrics if song else "Текст не найден"
    except Exception as e:
        logger.error(f"Ошибка Genius API: {str(e)}")
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

# --- GUI для управления сервером на PyQt5 ---
class ServerSignals(QObject):
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.signals = ServerSignals()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setGeometry(300, 300, 400, 200)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Поля ввода
        self.port_entry = QLineEdit(str(DEFAULT_PORT))
        self.db_entry = QLineEdit(DEFAULT_DATABASE_URL)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Порт:"))
        input_layout.addWidget(self.port_entry)
        
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Путь к БД:"))
        db_layout.addWidget(self.db_entry)
        
        # Кнопки
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.exit_btn = QPushButton("Exit")
        
        self.stop_btn.setEnabled(False)
        
        # Статус бар
        self.status_bar = QStatusBar()
        
        # Сборка интерфейса
        layout.addLayout(input_layout)
        layout.addLayout(db_layout)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.exit_btn)
        layout.addWidget(self.status_bar)
        
        # Подключение сигналов
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.exit_btn.clicked.connect(self.close)

    def start_server(self):
        if not self.server_thread or not self.server_thread.is_alive():
            port = int(self.port_entry.text())
            db_url = self.db_entry.text()
            
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(
                    app, 
                    host="0.0.0.0", 
                    port=port,
                    log_config=LOGGING_CONFIG
                ),
                daemon=True
            )
            self.server_thread.start()
            self.status_bar.showMessage(f"Сервер запущен на порту {port}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            QMessageBox.information(self, "Info", f"Сервер запущен на порту {port}")

    def stop_server(self):
        if self.server_thread and self.server_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.shutdown_server(), asyncio.new_event_loop())
            self.status_bar.showMessage("Сервер остановлен")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            QMessageBox.information(self, "Info", "Сервер остановлен")

    @staticmethod
    async def shutdown_server():
        await uvicorn.Server(uvicorn.Config(app)).shutdown()

if __name__ == "__main__":
    import sys
    server_app = QApplication(sys.argv)
    gui = ServerGUI()
    gui.show()
    sys.exit(server_app.exec_())
