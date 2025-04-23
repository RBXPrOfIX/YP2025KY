import sys
import logging
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QStatusBar, QSplitter, QHeaderView
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPalette, QColor

# Конфигурация
SERVER_URL = "http://localhost:8000"
TIMEOUT = 300.0
LOG_FILE = "client.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Поток для API вызовов
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

# Основное окно клиента
class LyricsClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.last_track = None
        self.last_artist = None
        self._apply_style()
        self._init_ui()

    def _apply_style(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f5f5f5"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
        palette.setColor(QPalette.Text, QColor("#333333"))
        palette.setColor(QPalette.Button, QColor("#4a6fa5"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(palette)

        style = """
        QLineEdit { border: 1px solid #ccc; border-radius: 4px; padding: 6px; font-size: 14px; }
        QPushButton { background-color: #4a6fa5; color: white; border: none; border-radius: 4px; padding: 8px 12px; font-size: 14px; min-width: 80px; }
        QPushButton:hover { background-color: #3b5980; }
        QTextEdit { border: 1px solid #ccc; border-radius: 4px; padding: 6px; font-size: 14px; background-color: #ffffff; }
        QTreeWidget { border: 1px solid #ccc; border-radius: 4px; font-size: 13px; background-color: #ffffff; }
        QHeaderView::section { background-color: #e0e0e0; padding: 4px; border: none; font-weight: bold; }
        QStatusBar { background-color: #e0e0e0; padding: 2px; }
        """
        self.setStyleSheet(style)

    def _init_ui(self):
        self.setWindowTitle("AI Assistant - Клиент")
        self.setGeometry(100, 100, 900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        search_layout = QHBoxLayout()
        self.track_input = QLineEdit(placeholderText="Название трека")
        self.artist_input = QLineEdit(placeholderText="Исполнитель")
        font = QFont(); font.setPointSize(13)
        self.track_input.setFont(font); self.artist_input.setFont(font)
        btn_search = QPushButton("Найти текст")
        btn_search.clicked.connect(self.start_search)
        search_layout.addWidget(QLabel("Трек:")); search_layout.addWidget(self.track_input)
        search_layout.addWidget(QLabel("Исполнитель:")); search_layout.addWidget(self.artist_input)
        search_layout.addWidget(btn_search)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        lyrics_container = QWidget()
        lyrics_layout = QVBoxLayout(lyrics_container)
        lyrics_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_layout.addWidget(QLabel("Текст песни:"))
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlaceholderText("Текст песни появится здесь...")
        lyrics_layout.addWidget(self.lyrics_area)
        splitter.addWidget(lyrics_container)

        similar_container = QWidget()
        similar_layout = QVBoxLayout(similar_container)
        similar_layout.setContentsMargins(0, 0, 0, 0)
        similar_layout.addWidget(QLabel("Похожие треки:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Исполнитель", "Трек", "Схожесть, %", "Разница тона"])
        self.tree.setMinimumWidth(350)
        self.tree.setColumnWidth(0, 200)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        similar_layout.addWidget(self.tree)
        btn_sim = QPushButton("Обновить похожие")
        btn_sim.clicked.connect(self.load_similar)
        similar_layout.addWidget(btn_sim)
        splitter.addWidget(similar_container)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        main_layout.addLayout(search_layout)
        main_layout.addWidget(splitter)

    def start_search(self):
        track = self.track_input.text().strip(); artist = self.artist_input.text().strip()
        if not track or not artist:
            self.status_bar.showMessage("Заполните все поля!", 3000); return
        self.last_track, self.last_artist = track, artist
        self.worker = ApiWorker("get_lyrics", {"track_name": track, "artist": artist})
        self.worker.finished.connect(self.on_lyrics); self.worker.error.connect(self.on_error)
        self.worker.start(); self.status_bar.showMessage("Запрос текста...")

    def on_lyrics(self, data):
        self.lyrics_area.setPlainText(data.get("lyrics", ""))
        self.status_bar.showMessage("Текст получен", 3000)

    def load_similar(self):
        if not self.last_track or not self.last_artist:
            self.status_bar.showMessage("Сначала найдите текст трека", 3000); return
        params = {"track_name": self.last_track, "artist": self.last_artist}
        self.worker = ApiWorker("find_similar", params)
        self.worker.finished.connect(self.on_similar); self.worker.error.connect(self.on_error)
        self.worker.start(); self.status_bar.showMessage("Поиск похожих...")

    def on_similar(self, data):
        self.tree.clear()
        for item in data.get("similar_tracks", []):
            artist = item["artist"]; track = item["track"]
            perc = f"{item['similarity']:.2f}"; tone_diff = f"{item['tone_difference']:.3f}"
            QTreeWidgetItem(self.tree, [artist, track, perc, tone_diff])
        cnt = self.tree.topLevelItemCount()
        self.status_bar.showMessage(f"Найдено {cnt} треков", 3000)

    def on_item_double_clicked(self, item, column):
        artist = item.text(0); track = item.text(1)
        self.track_input.setText(track); self.artist_input.setText(artist)
        self.start_search()

    def on_error(self, msg):
        self.status_bar.showMessage(msg, 5000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))
    win = LyricsClient()
    win.show()
    sys.exit(app.exec_())
