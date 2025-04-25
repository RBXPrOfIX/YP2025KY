import logging
import requests
import json
from PyQt5.QtCore import QThread, pyqtSignal

from lyrics_insight.config import SERVER_URL, TIMEOUT
from lyrics_insight.crypto import encrypt_request, decrypt_response

class ApiWorker(QThread):
    """
    Поток для выполнения зашифрованных API-запросов без блокировки UI.
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, endpoint, params=None):
        super().__init__()
        self.endpoint = endpoint
        self.params = params or {}

    def run(self):
        try:
            # Шифруем параметры запроса
            token = encrypt_request(self.params)
            resp = requests.post(
                f"{SERVER_URL}/{self.endpoint}",
                json={"data": token},
                timeout=TIMEOUT
            )
            if resp.status_code == 200:
                body = resp.json()
                encrypted = body.get("data")
                if not encrypted:
                    self.error.emit("Пустой ответ сервера")
                    return
                # Дешифруем и парсим
                data = decrypt_response(encrypted)
                self.finished.emit(data)
            else:
                self.error.emit(f"Сервер вернул {resp.status_code}")
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {e}")
            logging.error(f"Ошибка запроса: {e}")