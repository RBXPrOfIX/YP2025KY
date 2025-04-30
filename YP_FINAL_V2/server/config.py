import os
import logging.config
from dotenv import load_dotenv
load_dotenv()

# --- Основные настройки ---
DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
DEFAULT_PORT = int(os.getenv("PORT", 8000))

# --- API токены ---
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"

# --- Логирование ---
LOG_FILE = "server.log"
LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "file": {"class": "logging.FileHandler", "filename": LOG_FILE, "formatter": "default"},
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "formatters": {"default": {"format": "%(asctime)s - %(levelname)s - %(message)s"}},
    "root": {"handlers": ["file", "console"], "level": "INFO"},
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Гиперпараметры для /find_similar ---
SBERT_WEIGHT         = float(os.getenv("SBERT_WEIGHT",         "0.35"))  # семантика текста
E5_WEIGHT            = float(os.getenv("E5_WEIGHT",            "0.35"))  # глубокая семантика
EMO_WEIGHT           = float(os.getenv("EMO_WEIGHT",           "0.30"))  # эмоции в доп.весе

THEME_BONUS          = float(os.getenv("THEME_BONUS",          "0.25"))  # темы чуть ниже жанра
GENRE_BONUS          = float(os.getenv("GENRE_BONUS",          "0.50"))  # жанр важен, но не доминирует
OVERLAP_RATIO_BONUS  = float(os.getenv("OVERLAP_RATIO_BONUS",  "0.10"))  # умеренный буст пересечения

LENGTH_NORMALIZATION = int(os.getenv("LENGTH_NORMALIZATION",   "200"))
DUPLICATE_PENALTY    = float(os.getenv("DUPLICATE_PENALTY",     "0.05"))  # почти исключает оригинал