import sys
import logging
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QStatusBar, QSplitter, QProgressBar,
    QSizePolicy, QToolButton
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPainter, QPixmap, QPen

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
            response = requests.get(f"{SERVER_URL}/{self.endpoint}",
                                    params=self.params,
                                    timeout=TIMEOUT)
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"Сервер вернул {response.status_code}")
        except Exception as e:
            self.error.emit(f"Сетевая ошибка: {e}")
            logging.error(f"Ошибка запроса: {e}")


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._startPos = None
        self.setFixedHeight(32)
        self.setObjectName("TitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        self.titleLabel = QLabel(parent.windowTitle(), self)
        font = QFont(); font.setPointSize(10); font.setBold(True)
        self.titleLabel.setFont(font)
        layout.addWidget(self.titleLabel)
        layout.addStretch()

        self.btns = []
        for sp, handler in (
            (self.style().SP_TitleBarMinButton, parent.showMinimized),
            (self.style().SP_TitleBarMaxButton, self.toggle_max_restore),
            (self.style().SP_TitleBarCloseButton, parent.close),
        ):
            btn = QToolButton(self)
            btn.setFixedSize(32, 32)
            btn.clicked.connect(handler)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setIcon(self.style().standardIcon(sp))
            layout.addWidget(btn)
            self.btns.append((btn, sp))

    def toggle_max_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._startPos = event.globalPos() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._startPos and event.buttons() == Qt.LeftButton:
            self.parent.move(event.globalPos() - self._startPos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.toggle_max_restore()

    def set_light_theme(self):
        base_bg = "#f5f5f5"
        self.setStyleSheet(
            "#TitleBar { background-color: #ffffff; border-top-left-radius:10px; border-top-right-radius:10px; }"
            "QLabel { color:#000000; }"
        )
        icon_size = 16
        for btn, sp in self.btns:
            pix = QPixmap(icon_size, icon_size)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(Qt.black); pen.setWidth(2)
            painter.setPen(pen)
            if sp == self.style().SP_TitleBarMinButton:
                y = icon_size // 2
                painter.drawLine(2, y, icon_size - 2, y)
            elif sp == self.style().SP_TitleBarMaxButton:
                inset = 2
                painter.drawRect(inset, inset, icon_size - 2*inset, icon_size - 2*inset)
            else:
                painter.drawLine(2, 2, icon_size - 2, icon_size - 2)
                painter.drawLine(icon_size - 2, 2, 2, icon_size - 2)
            painter.end()
            btn.setIcon(QIcon(pix))
            hover = "#d0d0d0" if sp != self.style().SP_TitleBarCloseButton else "#e81123"
            btn.setStyleSheet(
                f"QToolButton {{ background-color:{base_bg}; border:none; }}\n"
                f"QToolButton:hover {{ background-color:{hover}; }}"
            )

    def set_dark_theme(self):
        base_bg = "#000000"
        self.setStyleSheet(
            "#TitleBar { background-color:#000000; border-top-left-radius:10px; border-top-right-radius:10px; }"
            "QLabel { color:#ffffff; }"
        )
        icon_size = 16
        for btn, sp in self.btns:
            pix = QPixmap(icon_size, icon_size)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(Qt.white); pen.setWidth(2)
            painter.setPen(pen)
            if sp == self.style().SP_TitleBarMinButton:
                y = icon_size // 2
                painter.drawLine(2, y, icon_size - 2, y)
            elif sp == self.style().SP_TitleBarMaxButton:
                inset = 2
                painter.drawRect(inset, inset, icon_size - 2*inset, icon_size - 2*inset)
            else:
                painter.drawLine(2, 2, icon_size - 2, icon_size - 2)
                painter.drawLine(icon_size - 2, 2, 2, icon_size - 2)
            painter.end()
            btn.setIcon(QIcon(pix))
            hover = "#333333" if sp != self.style().SP_TitleBarCloseButton else "#e81123"
            btn.setStyleSheet(
                f"QToolButton {{ background-color:{base_bg}; border:none; }}\n"
                f"QToolButton:hover {{ background-color:{hover}; }}"
            )


class LyricsPopup(QMainWindow):
    def __init__(self, title, lyrics, genre, artist, is_parent_dark):
        super().__init__()
        self.is_dark = is_parent_dark
        self.setWindowTitle(f"{title} — текст")
        self.setObjectName("PopupWindow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

        self.title_bar = TitleBar(self)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)

        lbl_artist = QLabel(f"Исполнитель: {artist}")
        lbl_track = QLabel(f"Трек: {title}")
        for lbl in (lbl_artist, lbl_track):
            lbl.setStyleSheet("font-size:14px; font-weight:bold;")
            body_layout.addWidget(lbl)

        content_layout = QHBoxLayout()
        left_col = QVBoxLayout(); left_col.setSpacing(4)
        left_col.addWidget(QLabel("Текст песни:"))
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlainText(lyrics)
        left_col.addWidget(self.lyrics_area, 1)
        content_layout.addLayout(left_col, 3)

        right_col = QVBoxLayout(); right_col.setSpacing(4)
        right_col.addWidget(QLabel("Жанры:"))
        self.genre_area = QTextEdit(readOnly=True)
        self.genre_area.setPlaceholderText("Жанры не найдены.")
        if genre:
            self.genre_area.setPlainText("\n".join(genre))
        right_col.addWidget(self.genre_area, 1)
        content_layout.addLayout(right_col, 1)

        body_layout.addLayout(content_layout)
        main_layout.addWidget(body)
        self.setCentralWidget(container)

        if self.is_dark:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

        self.resize(800, 500)
        self.show()

    def apply_light_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#f5f5f5"))
        pal.setColor(QPalette.Base, QColor("#ffffff"))
        pal.setColor(QPalette.Text, QColor("#333333"))
        self.setPalette(pal)
        self.setStyleSheet(self._light_style_sheet() + """
            #PopupWindow { border-radius:10px; background-color:#f5f5f5; }
            QWidget#body { background-color:#ffffff; }
        """)
        self.title_bar.set_light_theme()

    def apply_dark_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#000000"))
        pal.setColor(QPalette.Base, QColor("#121212"))
        pal.setColor(QPalette.Text, QColor("#E0E0E0"))
        self.setPalette(pal)
        self.setStyleSheet(self._dark_style_sheet() + """
            #PopupWindow { border-radius:10px; background-color:#000000; }
            QWidget#body { background-color:#121212; }
        """)
        self.title_bar.set_dark_theme()

    def _light_style_sheet(self):
        return """
        QTextEdit {
            background:#ffffff; color:#333333;
            border:1px solid #ccc; border-radius:4px; padding:6px;
        }
        QTextEdit QScrollBar:vertical {
            width:12px; background:#e0e0e0; margin:0px;
        }
        QTextEdit QScrollBar::handle:vertical {
            background:#888; min-height:20px; border-radius:6px;
        }
        QTextEdit QScrollBar::handle:vertical:hover {
            background:#555;
        }
        QTextEdit QScrollBar::add-line, QTextEdit QScrollBar::sub-line {
            height:0px;
        }
        QLabel { color:#333333; }
        """

    def _dark_style_sheet(self):
        return """
        QTextEdit {
            background:#121212; color:#E0E0E0;
            border:1px solid #555; border-radius:4px; padding:6px;
        }
        QTextEdit QScrollBar:vertical {
            width:12px; background:#333333; margin:0px;
        }
        QTextEdit QScrollBar::handle:vertical {
            background:#666666; min-height:20px; border-radius:6px;
        }
        QTextEdit QScrollBar::handle:vertical:hover {
            background:#888888;
        }
        QTextEdit QScrollBar::add-line, QTextEdit QScrollBar::sub-line {
            height:0px;
        }
        QLabel { color:#E0E0E0; }
        """


class LyricsClient(QMainWindow):
    _threads = []

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lyrics Insight")
        self.setObjectName("MainWindow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.is_dark = False
        self.dialogs = []

        self.title_bar = TitleBar(self)
        self._initialize_ui()
        self.apply_light_theme()
        self.resize(1024, 768)

    def apply_light_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#f5f5f5"))
        pal.setColor(QPalette.Base, QColor("#ffffff"))
        pal.setColor(QPalette.Text, QColor("#333333"))
        pal.setColor(QPalette.Button, QColor("#4a6fa5"))
        pal.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(pal)
        self.setStyleSheet(self._light_style_sheet() + "#MainWindow{border-radius:10px;}")
        self.title_bar.set_light_theme()
        self.is_dark = False
        # Синхронизируем все всплывающие
        for dlg in self.dialogs:
            dlg.is_dark = False
            dlg.apply_light_theme()

    def apply_dark_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#000000"))
        pal.setColor(QPalette.Base, QColor("#121212"))
        pal.setColor(QPalette.Text, QColor("#E0E0E0"))
        pal.setColor(QPalette.Button, QColor("#D32F2F"))
        pal.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(pal)
        self.setStyleSheet(self._dark_style_sheet() + "#MainWindow{border-radius:10px;}")
        self.title_bar.set_dark_theme()
        self.is_dark = True
        # Синхронизируем все всплывающие
        for dlg in self.dialogs:
            dlg.is_dark = True
            dlg.apply_dark_theme()

    def _light_style_sheet(self):
        return """
        QLineEdit, QTreeWidget {
            border:1px solid #ccc; border-radius:4px; padding:6px; background:#fff;
        }
        QTextEdit {
            background:#ffffff; color:#333333;
            border:1px solid #ccc; border-radius:4px; padding:6px;
        }
        QTextEdit QScrollBar:vertical {
            width:12px; background:#e0e0e0; margin:0px;
        }
        QTextEdit QScrollBar::handle:vertical {
            background:#888; min-height:20px; border-radius:6px;
        }
        QTextEdit QScrollBar::handle:vertical:hover {
            background:#555;
        }
        QTextEdit QScrollBar::add-line, QTextEdit QScrollBar::sub-line {
            height:0px;
        }
        QPushButton { background:#4a6fa5; color:#fff; border:none; border-radius:4px; padding:8px 12px; }
        QPushButton:hover { background:#3b5980; }
        QHeaderView::section { background:#e0e0e0; padding:4px; border:none; font-weight:bold; }
        QStatusBar { background:#e0e0e0; padding:2px; }
        QProgressBar { border:1px solid #aaa; border-radius:10px; background:#e8edf2; height:14px; text-align:center; }
        QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #99ccff,stop:1 #4a90e2); border-radius:10px; }
        """

    def _dark_style_sheet(self):
        return """
        QLineEdit, QTreeWidget {
            border:1px solid #555; border-radius:4px; padding:6px; background:#333; color:#E0E0E0;
        }
        QTextEdit {
            background:#121212; color:#E0E0E0;
            border:1px solid #555; border-radius:4px; padding:6px;
        }
        QTextEdit QScrollBar:vertical {
            width:12px; background:#333333; margin:0px;
        }
        QTextEdit QScrollBar::handle:vertical {
            background:#666666; min-height:20px; border-radius:6px;
        }
        QTextEdit QScrollBar::handle:vertical:hover {
            background:#888888;
        }
        QTextEdit QScrollBar::add-line, QTextEdit QScrollBar::sub-line {
            height:0px;
        }
        QPushButton { background:#D32F2F; color:#fff; border:none; border-radius:4px; padding:8px 12px; }
        QPushButton:hover { background:#B71C1C; }
        QHeaderView::section { background:#444; padding:4px; border:none; font-weight:bold; color:#E0E0E0; }
        QStatusBar { background:#222; padding:2px; color:#E0E0E0; }
        QProgressBar { border:1px solid #555; border-radius:10px; background:#444; height:14px; text-align:center; }
        QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff8a80,stop:1 #ff1744); border-radius:10px; }
        QMainWindow { background:#000; }
        QLabel { color:#E0E0E0; }
        """

    def _initialize_ui(self):
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)

        body_layout.addLayout(self._create_search_bar())

        self.theme_btn = QPushButton()
        self.theme_btn.setFixedSize(38, 38)
        self.theme_btn.setFont(QFont("Segoe UI Symbol", 14))
        self.theme_btn.setToolTip("Переключить тему")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self._update_theme_icon()
        th_layout = QHBoxLayout()
        th_layout.addStretch()
        th_layout.addWidget(self.theme_btn)
        body_layout.addLayout(th_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(14)
        self.progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        body_layout.addWidget(self.progress)

        splitter = self._create_splitter()
        body_layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        body_layout.addWidget(self.status_bar)

        main_layout.addWidget(body)
        self.setCentralWidget(container)

    def _update_theme_icon(self):
        self.theme_btn.setText("☼" if not self.is_dark else "☾")

    def _create_search_bar(self):
        layout = QHBoxLayout()
        self.track_label = QLabel("Трек:")
        self.track_input = QLineEdit(placeholderText="Название трека")
        self.artist_label = QLabel("Исполнитель:")
        self.artist_input = QLineEdit(placeholderText="Исполнитель")
        font = QFont()
        font.setPointSize(13)
        self.track_input.setFont(font)
        self.artist_input.setFont(font)
        btn = QPushButton("Найти текст")
        btn.clicked.connect(self.start_search)
        layout.addWidget(self.track_label)
        layout.addWidget(self.track_input)
        layout.addWidget(self.artist_label)
        layout.addWidget(self.artist_input)
        layout.addWidget(btn)
        return layout

    def _create_splitter(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Текст песни:"))
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlaceholderText("Текст песни появится здесь...")
        left_layout.addWidget(self.lyrics_area, 1)
        left = QWidget()
        left.setLayout(left_layout)

        right_layout = QVBoxLayout()
        self.similar_label = QLabel("Похожие треки:")
        right_layout.addWidget(self.similar_label)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "Исполнитель", "Трек", "Схожесть, %", "Разница тона"])
        self.tree.setColumnWidth(0, 24)
        self.tree.setColumnWidth(1, 200)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        right_layout.addWidget(self.tree, 1)
        btn_sim = QPushButton("Обновить похожие")
        btn_sim.clicked.connect(self.load_similar)
        right_layout.addWidget(btn_sim)
        right = QWidget()
        right.setLayout(right_layout)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        return splitter

    def toggle_theme(self):
        if self.is_dark:
            self.apply_light_theme()
        else:
            self.apply_dark_theme()

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
        self._run_worker("find_similar", {"track_name": self.last_track, "artist": self.last_artist}, self.on_similar)

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
            artist = item["artist"]
            track = item["track"]
            sim = item["similarity"]
            tone = item["tone_diff"]
            node = QTreeWidgetItem(["", artist, track, f"{sim:.2f}", f"{tone:.3f}"])
            self._apply_similarity_color(node, sim)
            self.tree.addTopLevelItem(node)
        self.status_bar.showMessage(f"Найдено {self.tree.topLevelItemCount()} треков", 3000)

    def _apply_similarity_color(self, node, sim):
        if sim > 85:
            color = QColor("#4caf50")
        elif sim >= 70:
            color = QColor("#aed581")
        elif sim >= 55:
            color = QColor("#ffeb3b")
        else:
            color = QColor("#f44336")
        size = 12
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        node.setIcon(0, QIcon(pix))

    def on_item_double_clicked(self, item, _):
        self._cleanup_threads()
        artist = item.text(1)
        track = item.text(2)
        worker = ApiWorker("get_lyrics", {"track_name": track, "artist": artist})
        worker.finished.connect(
            lambda data: self.show_lyrics_popup(track, data.get("lyrics", ""), data.get("genre", []), artist)
        )
        worker.error.connect(lambda m: self.status_bar.showMessage(m, 5000))
        self._threads.append(worker)
        worker.start()

    def show_lyrics_popup(self, title, lyrics, genre, artist):
        popup = LyricsPopup(title, lyrics, genre, artist, self.is_dark)
        self.dialogs.append(popup)


    def _cleanup_threads(self):
        self._threads = [t for t in self._threads if t.isRunning()]

    def on_error(self, msg):
        self.status_bar.showMessage(msg, 5000)


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 11))
    window = LyricsClient()
    window.show()
    sys.exit(app.exec_())
