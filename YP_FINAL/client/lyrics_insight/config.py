import logging
from dotenv import load_dotenv
load_dotenv()  # подгрузить переменные из .env

# Конфигурация сервера и логирования
SERVER_URL = "http://localhost:8000"
TIMEOUT = 300.0
LOG_FILE = "client.log"

def setup_logging():
    """
    Настраивает логирование в файл с необходимым форматом.
    """
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )