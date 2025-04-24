# client.py
import sys
import logging
import platform
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QStatusBar
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

# Конфигурация
SERVER_URL = "http://localhost:8000"
TIMEOUT = 10.0
LOG_FILE = "client.log"

# Настройка логгера
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class ApiWorker(QThread):
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
                self.error.emit(f"Ошибка сервера: {response.status_code}")
                
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {str(e)}")
            logging.error(f"Ошибка запроса: {str(e)}")

class ServerPingWorker(QThread):
    finished = pyqtSignal(bool)

    def run(self):
        try:
            requests.get(f"{SERVER_URL}/find_similar", timeout=3)
            self.finished.emit(True)
        except Exception:
            self.finished.emit(False)

class LyricsClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Assistant - Клиент")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()
        self.check_server_status()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Поисковая панель
        search_layout = QHBoxLayout()
        self.track_input = QLineEdit(placeholderText="Название трека")
        self.artist_input = QLineEdit(placeholderText="Исполнитель")
        search_btn = QPushButton("Найти текст")
        search_btn.clicked.connect(self.start_search)
        
        search_layout.addWidget(QLabel("Трек:"))
        search_layout.addWidget(self.track_input)
        search_layout.addWidget(QLabel("Исполнитель:"))
        search_layout.addWidget(self.artist_input)
        search_layout.addWidget(search_btn)

        # Текст песни
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlaceholderText("Текст песни появится здесь...")

        # Похожие треки
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Исполнитель", "Трек"])
        self.tree_widget.setColumnWidth(0, 300)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        # Панель управления
        control_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить похожие")
        refresh_btn.clicked.connect(self.load_similar)
        self.status_bar = QStatusBar()
        
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()

        # Сборка интерфейса
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.lyrics_area)
        main_layout.addWidget(QLabel("Похожие треки:"))
        main_layout.addWidget(self.tree_widget)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.status_bar)

    def check_server_status(self):
        self.ping_worker = ServerPingWorker()
        self.ping_worker.finished.connect(self.handle_ping_result)
        self.ping_worker.start()

    def handle_ping_result(self, status):
        if status:
            self.status_bar.showMessage("✓ Сервер доступен", 5000)
        else:
            self.status_bar.showMessage("✗ Сервер недоступен", 5000)

    def start_search(self):
        track = self.track_input.text().strip()
        artist = self.artist_input.text().strip()
        
        if not track or not artist:
            self.status_bar.showMessage("Заполните все поля!", 3000)
            return
            
        self.worker = ApiWorker("get_lyrics", {
            "track_name": track, 
            "artist": artist
        })
        self.worker.finished.connect(self.handle_lyrics_response)
        self.worker.error.connect(self.show_error)
        self.worker.start()
        self.status_bar.showMessage("Поиск текста...")

    def load_similar(self):
        self.worker = ApiWorker("find_similar")
        self.worker.finished.connect(self.handle_similar_response)
        self.worker.error.connect(self.show_error)
        self.worker.start()
        self.status_bar.showMessage("Загрузка похожих треков...")

    def handle_lyrics_response(self, data):
        lyrics = data.get("lyrics", "Текст не найден")
        self.lyrics_area.setPlainText(lyrics)
        self.status_bar.showMessage("Готово", 3000)

    def handle_similar_response(self, data):
        self.tree_widget.clear()
        for track in data.get("similar_tracks", []):
            QTreeWidgetItem(self.tree_widget, [track["artist"], track["track"]])
        self.status_bar.showMessage(f"Найдено {self.tree_widget.topLevelItemCount()} треков", 3000)

    def show_error(self, message):
        self.status_bar.showMessage(message, 5000)
        self.lyrics_area.clear()

    def on_item_double_clicked(self, item, column):
        artist = item.text(0)
        track = item.text(1)
        
        self.worker = ApiWorker("get_lyrics", {
            "track_name": track, 
            "artist": artist
        })
        self.worker.finished.connect(self.handle_lyrics_response)
        self.worker.error.connect(self.show_error)
        self.worker.start()
        self.status_bar.showMessage(f"Поиск текста: {artist} - {track}...")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LyricsClient()
    window.show()
    sys.exit(app.exec_())