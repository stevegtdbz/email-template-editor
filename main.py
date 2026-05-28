import sys
from PyQt6.QtWidgets import QApplication
from app.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
