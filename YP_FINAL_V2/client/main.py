import sys
import signal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from lyrics_insight.config import setup_logging
from lyrics_insight.main_window import LyricsClient

if __name__ == "__main__":
    setup_logging()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 11))
    window = LyricsClient()
    window.show()
    sys.exit(app.exec_())