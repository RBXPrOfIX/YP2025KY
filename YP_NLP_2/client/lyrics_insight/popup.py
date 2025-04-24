from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor

from lyrics_insight.titlebar import TitleBar

class LyricsPopup(QMainWindow):
    """
    Всплывающее окно для отображения текста песни и жанров.
    """
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
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_col.addWidget(QLabel("Текст песни:"))
        self.lyrics_area = QTextEdit(readOnly=True)
        self.lyrics_area.setPlainText(lyrics)
        left_col.addWidget(self.lyrics_area, 1)
        content_layout.addLayout(left_col, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
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