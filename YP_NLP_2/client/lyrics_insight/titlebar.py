from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QPen

class TitleBar(QWidget):
    """
    Кастомный заголовок окна с кнопками свернуть, развернуть и закрыть,
    а также возможностью перемещения окна.
    """
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
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.titleLabel.setFont(font)
        layout.addWidget(self.titleLabel)
        layout.addStretch()

        self.btns = []
        # Иконки работы кнопок стандартными стилями
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
            pen = QPen(Qt.black)
            pen.setWidth(2)
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
            pen = QPen(Qt.white)
            pen.setWidth(2)
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