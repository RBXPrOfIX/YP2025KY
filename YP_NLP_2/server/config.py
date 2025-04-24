# server/config.py
import os
import logging.config

# --- Основные настройки ---
DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
DEFAULT_PORT = int(os.getenv("PORT", 8000))

# --- API токены ---
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN", "OheKD5f6K0vm_3aKWGfb5wE8Et4bkt_TTzXRVWcRr1Ywlb8VU1yMxVC6dATKMiw7")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "3bfa7b7aa77348f7de800e8f90af0a51")
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

# --- Логирование ---
LOG_FILE = "server.log"
LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_FILE,
            "formatter": "default"
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default"
        },
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s"
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO",
    },
}

# Инициализация логгера
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
