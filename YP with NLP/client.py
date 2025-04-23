# client.py
import sys
import logging
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QStatusBar
)
from PyQt5.QtCore import QThread, pyqtSignal

SERVER_URL = "http://localhost:8000"
TIMEOUT = 300.0
LOG_FILE = "client.log"

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
            resp = requests.get(f"{SERVER_URL}/{self.endpoint}", params=self.params, timeout=TIMEOUT)
            if resp.status_code == 200:
                self.finished.emit(resp.json())
            else:
                self.error.emit(f"Сервер вернул {resp.status_code}")
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {e}")
            logging.error(f"Ошибка запроса: {e}")

class LyricsClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.last_track = None
        self.last_artist = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("AI Assistant - Клиент")
        self.setGeometry(100, 100, 800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Поисковая панель
        hl = QHBoxLayout()
        self.track_input = QLineEdit(placeholderText="Название трека")
        self.artist_input = QLineEdit(placeholderText="Исполнитель")
        btn = QPushButton("Найти текст")
        btn.clicked.connect(self.start_search)
        hl.addWidget(QLabel("Трек:"))
        hl.addWidget(self.track_input)
        hl.addWidget(QLabel("Исполнитель:"))
        hl.addWidget(self.artist_input)
        hl.addWidget(btn)

        # Текст песни
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlaceholderText("Текст песни появится здесь...")

        # Похожие треки
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Исполнитель", "Трек", "Схожесть, %", "Разница тона"])
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        btn_sim = QPushButton("Обновить похожие")
        btn_sim.clicked.connect(self.load_similar)

        self.status_bar = QStatusBar()

        layout.addLayout(hl)
        layout.addWidget(self.lyrics_area)
        layout.addWidget(QLabel("Похожие треки:"))
        layout.addWidget(self.tree)
        layout.addWidget(btn_sim)
        layout.addWidget(self.status_bar)

    def start_search(self):
        track = self.track_input.text().strip()
        artist = self.artist_input.text().strip()
        if not track or not artist:
            self.status_bar.showMessage("Заполните все поля!", 3000)
            return
        self.last_track, self.last_artist = track, artist
        self.worker = ApiWorker("get_lyrics", {"track_name": track, "artist": artist})
        self.worker.finished.connect(self.on_lyrics)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_bar.showMessage("Запрос текста...")

    def on_lyrics(self, data):
        self.lyrics_area.setPlainText(data.get("lyrics", ""))
        self.status_bar.showMessage("Текст получен", 3000)

    def load_similar(self):
        if not self.last_track or not self.last_artist:
            self.status_bar.showMessage("Сначала найдите текст трека", 3000)
            return
        params = {"track_name": self.last_track, "artist": self.last_artist}
        self.worker = ApiWorker("find_similar", params)
        self.worker.finished.connect(self.on_similar)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_bar.showMessage("Поиск похожих...")

    def on_similar(self, data):
        self.tree.clear()
        for item in data.get("similar_tracks", []):
            artist = item["artist"]
            track = item["track"]
            perc = f"{item['similarity']:.2f}"
            tone_diff = f"{item['tone_difference']:.3f}"
            QTreeWidgetItem(self.tree, [artist, track, perc, tone_diff])
        cnt = self.tree.topLevelItemCount()
        self.status_bar.showMessage(f"Найдено {cnt} треков", 3000)

    def on_item_double_clicked(self, item, column):
        artist = item.text(0)
        track = item.text(1)
        self.track_input.setText(track)
        self.artist_input.setText(artist)
        self.start_search()

    def on_error(self, msg):
        self.status_bar.showMessage(msg, 5000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LyricsClient()
    win.show()
    sys.exit(app.exec_())