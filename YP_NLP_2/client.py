import sys
import logging
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QStatusBar, QSplitter, QHeaderView, QProgressBar, QSizePolicy
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


class ApiWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, endpoint, params=None):
        super().__init__()
        self.endpoint = endpoint
        self.params = params or {}

    def run(self):
        try:
            response = requests.get(f"{SERVER_URL}/{self.endpoint}", params=self.params, timeout=TIMEOUT)
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"Сервер вернул {response.status_code}")
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {e}")
            logging.error(f"Ошибка запроса: {e}")


class LyricsDialog(QWidget):
    def __init__(self, title, lyrics, genre=None, artist=""):
        super().__init__()
        self.setWindowTitle(f"{title} — текст")
        self.setGeometry(300, 300, 800, 500)
        self.setMinimumSize(500, 300)

        layout = QVBoxLayout(self)

        title_label = QLabel(f"Трек: {title}")
        artist_label = QLabel(f"Исполнитель: {artist}")
        for label in (title_label, artist_label):
            label.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
            layout.addWidget(label)

        content = QHBoxLayout()

        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("Текст песни:"))
        text_area = QTextEdit()
        text_area.setPlainText(lyrics)
        text_area.setReadOnly(True)
        text_layout.addWidget(text_area)

        genre_layout = QVBoxLayout()
        genre_layout.addWidget(QLabel("Жанры:"))
        genre_area = QTextEdit()
        genre_area.setReadOnly(True)
        genre_area.setPlaceholderText("Жанры не найдены.")
        if genre:
            genre_area.setPlainText("\n".join(genre))
        genre_layout.addWidget(genre_area)

        content.addLayout(text_layout, 3)
        content.addLayout(genre_layout, 1)
        layout.addLayout(content)

        self.show()


class LyricsClient(QMainWindow):
    _threads = []

    def __init__(self):
        super().__init__()
        self.is_dark = False
        self.dialogs = []
        # Инициализируем UI сначала
        self._initialize_ui()
        # Применяем светлую тему по умолчанию
        self.apply_light_theme()

    def apply_light_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f5f5f5"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
        palette.setColor(QPalette.Text, QColor("#333333"))
        palette.setColor(QPalette.Button, QColor("#4a6fa5"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(palette)
        self.setStyleSheet(self._light_style_sheet())
        # Сброс стилей меток
        self.track_label.setStyleSheet("")
        self.artist_label.setStyleSheet("")
        self.similar_label.setStyleSheet("")

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#000000"))
        palette.setColor(QPalette.Base, QColor("#121212"))
        palette.setColor(QPalette.AlternateBase, QColor("#1e1e1e"))
        palette.setColor(QPalette.Text, QColor("#E0E0E0"))
        palette.setColor(QPalette.Button, QColor("#D32F2F"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(palette)
        self.setStyleSheet(self._dark_style_sheet())
        # Подсветка меток
        self.track_label.setStyleSheet("color: #E0E0E0;")
        self.artist_label.setStyleSheet("color: #E0E0E0;")
        # Специально делаем текст 'Похожие треки:' чёрным
        self.similar_label.setStyleSheet("color: #000000;")

    def _light_style_sheet(self):
        return """
        QLineEdit, QTextEdit, QTreeWidget {
            border: 1px solid #ccc; border-radius: 4px; padding: 6px;
            font-size: 14px; background-color: #ffffff;
        }
        QPushButton {
            background-color: #4a6fa5; color: white; border: none;
            border-radius: 4px; padding: 8px 12px; font-size: 14px; min-width: 80px;
        }
        QPushButton:hover {
            background-color: #3b5980;
        }
        QHeaderView::section {
            background-color: #e0e0e0; padding: 4px; border: none; font-weight: bold;
        }
        QStatusBar {
            background-color: #e0e0e0; padding: 2px;
        }
        QProgressBar {
            border: 1px solid #aaa; border-radius: 10px; background: #e8edf2;
            height: 14px; text-align: center;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #99ccff, stop:1 #4a90e2);
            border-radius: 10px; width: 1px;
        }
        """

    def _dark_style_sheet(self):
        return """
        QLineEdit, QTextEdit, QTreeWidget {
            border: 1px solid #555; border-radius: 4px; padding: 6px;
            font-size: 14px; background-color: #333333; color: #E0E0E0;
        }
        QPushButton {
            background-color: #D32F2F; color: white; border: none;
            border-radius: 4px; padding: 8px 12px; font-size: 14px; min-width: 80px;
        }
        QPushButton:hover {
            background-color: #B71C1C;
        }
        QHeaderView::section {
            background-color: #444444; padding: 4px; border: none; font-weight: bold; color: #E0E0E0;
        }
        QStatusBar {
            background-color: #222222; padding: 2px; color: #E0E0E0;
        }
        QProgressBar {
            border: 1px solid #555; border-radius: 10px; background: #444444;
            height: 14px; text-align: center;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #ff8a80, stop:1 #ff1744);
            border-radius: 10px; width: 1px;
        }
        QMainWindow {
            background-color: #000000;
            border-top: 4px solid #000000;
        }
        QLabel { color: #E0E0E0; }
        """

    def _initialize_ui(self):
        self.setWindowTitle("Lyrics Insight")
        self.setGeometry(100, 100, 900, 650)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Панель поиска
        layout.addLayout(self._create_search_bar())

        # Кнопка переключения темы
        self.theme_btn = QPushButton("☀️")
        self.theme_btn.setFixedSize(32, 32)
        self.theme_btn.clicked.connect(self.toggle_theme)
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(self.theme_btn)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)

        # Прогрессбар
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(14)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.progress)

        # Основной сплиттер
        layout.addWidget(self._create_splitter())
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def toggle_theme(self):
        if self.is_dark:
            self.apply_light_theme()
            self.theme_btn.setText("☀️")
            self.is_dark = False
        else:
            self.apply_dark_theme()
            self.theme_btn.setText("🌙")
            self.is_dark = True

    def _create_search_bar(self):
        layout = QHBoxLayout()
        self.track_label = QLabel("Трек:")
        self.track_input = QLineEdit(placeholderText="Название трека")
        self.artist_label = QLabel("Исполнитель:")
        self.artist_input = QLineEdit(placeholderText="Исполнитель")
        font = QFont(); font.setPointSize(13)
        self.track_input.setFont(font); self.artist_input.setFont(font)
        search_btn = QPushButton("Найти текст")
        search_btn.clicked.connect(self.start_search)
        layout.addWidget(self.track_label); layout.addWidget(self.track_input)
        layout.addWidget(self.artist_label); layout.addWidget(self.artist_input)
        layout.addWidget(search_btn)
        return layout

    def _create_splitter(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        lyrics_box = QVBoxLayout()
        lyrics_box.addWidget(QLabel("Текст песни:"))
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlaceholderText("Текст песни появится здесь...")
        lyrics_box.addWidget(self.lyrics_area)
        left = QWidget(); left.setLayout(lyrics_box)

        similar_box = QVBoxLayout()
        # Сохраняем метку "Похожие треки:"
        self.similar_label = QLabel("Похожие треки:")
        similar_box.addWidget(self.similar_label)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Исполнитель", "Трек", "Схожесть, %", "Разница тона"])
        self.tree.setMinimumWidth(350)
        self.tree.setColumnWidth(0, 200)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        similar_box.addWidget(self.tree)

        sim_btn = QPushButton("Обновить похожие")
        sim_btn.clicked.connect(self.load_similar)
        similar_box.addWidget(sim_btn)
        right = QWidget(); right.setLayout(similar_box)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        return splitter

    def start_search(self):
        track = self.track_input.text().strip()
        artist = self.artist_input.text().strip()
        if not track or not artist:
            self.status_bar.showMessage("Заполните все поля!", 3000)
            return
        self.last_track, self.last_artist = track, artist
        self._run_worker("get_lyrics", {"track_name": track, "artist": artist}, self.on_lyrics)

    def load_similar(self):
        if not getattr(self, 'last_track', None) or not getattr(self, 'last_artist', None):
            self.status_bar.showMessage("Сначала найдите текст трека", 3000)
            return
        self._run_worker("find_similar", {
            "track_name": self.last_track,
            "artist": self.last_artist
        }, self.on_similar)

    def _run_worker(self, endpoint, params, callback):
        self._cleanup_threads()
        self.progress.setVisible(True)
        worker = ApiWorker(endpoint, params)
        worker.finished.connect(callback)
        worker.error.connect(self.on_error)
        worker.finished.connect(lambda: self.progress.setVisible(False))
        worker.error.connect(lambda: self.progress.setVisible(False))
        self._threads.append(worker)
        worker.start()

    def on_lyrics(self, data):
        self.lyrics_area.setPlainText(data.get("lyrics", ""))
        self.status_bar.showMessage("Текст получен", 3000)

    def on_similar(self, data):
        self.tree.clear()
        for item in data.get("similar_tracks", []):
            node = QTreeWidgetItem([
                item["artist"], item["track"],
                f"{item['similarity']:.2f}",
                f"{item['tone_diff']:.3f}" 
            ])
            self._apply_similarity_color(node, item['similarity'])
            self.tree.addTopLevelItem(node)
        self.status_bar.showMessage(f"Найдено {self.tree.topLevelItemCount()} треков", 3000)

    def _apply_similarity_color(self, node, similarity):
        if similarity >= 85:
            color = QColor("#c8e6c9")
        elif similarity >= 70:
            color = QColor("#e6f4ea")
        elif similarity >= 50:
            color = QColor("#fffde7")
        else:
            return
        # Устанавливаем цвет текста согласно теме
        if self.is_dark:
            node.setForeground(0, QColor("#000000"))
            node.setForeground(1, QColor("#000000"))
            node.setForeground(2, QColor("#000000"))
            node.setForeground(3, QColor("#000000"))
        for i in range(4):
            node.setBackground(i, color)

    def on_item_double_clicked(self, item, _):
        self._cleanup_threads()
        artist = item.text(0)
        track = item.text(1)
        worker = ApiWorker("get_lyrics", {"track_name": track, "artist": artist})
        worker.finished.connect(lambda data: self.show_lyrics_popup(track, data.get("lyrics", ""), data.get("genre", []), artist))
        worker.error.connect(lambda msg: self.status_bar.showMessage(msg, 5000))
        self._threads.append(worker)
        worker.start()

    def show_lyrics_popup(self, title, lyrics, genre, artist):
        self._cleanup_threads()
        dialog = LyricsDialog(title, lyrics, genre, artist)
        self.dialogs.append(dialog)

    def _cleanup_threads(self):
        self._threads = [t for t in self._threads if t.isRunning()]

    def on_error(self, message):
        self.status_bar.showMessage(message, 5000)


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 11))
    window = LyricsClient()
    window.show()
    sys.exit(app.exec_())
