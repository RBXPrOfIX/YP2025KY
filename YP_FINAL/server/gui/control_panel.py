# server/gui/control_panel.py
import threading
import asyncio
import uvicorn

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStatusBar, QMessageBox
)

from config import DEFAULT_PORT, DEFAULT_DATABASE_URL, LOGGING_CONFIG
from ..main import app


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Server Control Panel")
        self.setGeometry(300, 300, 400, 200)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Порт и БД
        self.port_entry = QLineEdit(str(DEFAULT_PORT))
        self.db_entry = QLineEdit(DEFAULT_DATABASE_URL)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Порт:"))
        port_layout.addWidget(self.port_entry)

        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Путь к БД:"))
        db_layout.addWidget(self.db_entry)

        # Кнопки
        self.start_btn = QPushButton("Запустить сервер")
        self.stop_btn = QPushButton("Остановить сервер")
        self.exit_btn = QPushButton("Выход")
        self.stop_btn.setEnabled(False)

        self.status_bar = QStatusBar()

        layout.addLayout(port_layout)
        layout.addLayout(db_layout)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.exit_btn)
        layout.addWidget(self.status_bar)

        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.exit_btn.clicked.connect(self.close)

    def start_server(self):
        if not self.server_thread or not self.server_thread.is_alive():
            port = int(self.port_entry.text())
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(app, host="0.0.0.0", port=port, log_config=LOGGING_CONFIG),
                daemon=True
            )
            self.server_thread.start()
            self.status_bar.showMessage(f"Сервер запущен на порту {port}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            QMessageBox.information(self, "Info", f"Сервер запущен на порту {port}")

    def stop_server(self):
        if self.server_thread and self.server_thread.is_alive():
            asyncio.run_coroutine_threadsafe(self.shutdown_server(), asyncio.new_event_loop())
            self.status_bar.showMessage("Сервер остановлен")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            QMessageBox.information(self, "Info", "Сервер остановлен")

    @staticmethod
    async def shutdown_server():
        await uvicorn.Server(uvicorn.Config(app)).shutdown()


if __name__ == "__main__":
    import sys
    app_qt = QApplication(sys.argv)
    gui = ServerGUI()
    gui.show()
    sys.exit(app_qt.exec_())
