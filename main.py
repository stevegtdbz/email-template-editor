import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from app.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Allow local HTML files to load remote images / fonts / stylesheets
    _s = QWebEngineProfile.defaultProfile().settings()
    _s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    _s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

    window = MainWindow()
    window.show()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
