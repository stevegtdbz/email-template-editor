from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from app import styles


class TopBar(QWidget):
    open_folder_requested = pyqtSignal()
    load_guide_requested  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"background:{styles.BG_MID};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self._path_label = QLabel("No folder selected")
        self._path_label.setStyleSheet(f"color:{styles.TEXT_MUTED}; font-size:13px;")
        layout.addWidget(self._path_label)

        layout.addStretch()

        self._guide_label = QLabel("No guide loaded")
        self._guide_label.setStyleSheet(f"color:#6b7280; font-size:12px;")
        layout.addWidget(self._guide_label)

        guide_btn = QPushButton("Load Guide…")
        guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        guide_btn.setStyleSheet("""
            QPushButton {
                background:#1e3a5f; color:#93c5fd;
                border:1px solid #2563eb; border-radius:5px;
                padding:5px 14px; font-size:13px;
            }
            QPushButton:hover  { background:#1e40af; color:white; }
            QPushButton:pressed{ background:#1d4ed8; }
        """)
        guide_btn.clicked.connect(self.load_guide_requested)
        layout.addWidget(guide_btn)

        open_btn = QPushButton("Open Folder…")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background:{styles.ACCENT}; color:white;
                border:none; border-radius:5px;
                padding:6px 16px; font-size:13px;
            }}
            QPushButton:hover  {{ background:#0b5ed7; }}
            QPushButton:pressed{{ background:#094db5; }}
        """)
        open_btn.clicked.connect(self.open_folder_requested)
        layout.addWidget(open_btn)

    def set_path(self, path: str) -> None:
        self._path_label.setText(path)

    def set_guide(self, name: str) -> None:
        self._guide_label.setText(f"Guide: {name}")
        self._guide_label.setStyleSheet("color:#93c5fd; font-size:12px;")
