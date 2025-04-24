import logging
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from lyrics_insight.config import SERVER_URL, TIMEOUT

class ApiWorker(QThread):
    """
    Поток для выполнения API-запросов без блокировки UI.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, endpoint, params=None):
        super().__init__()
        self.endpoint = endpoint
        self.params = params or {}

    def run(self):
        try:
            response = requests.get(
                f"{SERVER_URL}/{self.endpoint}",
                params=self.params,
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"Сервер вернул {response.status_code}")
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {e}")
            logging.error(f"Ошибка запроса: {e}")