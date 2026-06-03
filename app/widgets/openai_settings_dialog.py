from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton,
)
from PyQt6.QtCore import Qt
from app import style_store


class OpenAISettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenAI API Key")
        self.setFixedWidth(460)
        self.setStyleSheet("background:#2b2d30; color:#e5e7eb;")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("OpenAI API Key")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#e5e7eb;")
        layout.addWidget(title)

        hint = QLabel(
            "Your key is stored locally in your home directory and never sent anywhere "
            "except the OpenAI API."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9ca3af; font-size:12px;")
        layout.addWidget(hint)

        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("sk-…")
        self._key_input.setText(style_store.load_openai_key())
        self._key_input.setStyleSheet("""
            QLineEdit {
                background:#1a1b1e; color:#e5e7eb;
                border:1px solid #3c3f41; border-radius:4px;
                padding:8px 10px; font-size:13px; font-family:monospace;
            }
            QLineEdit:focus { border-color:#4f46e5; }
        """)
        layout.addWidget(self._key_input)

        show_btn = QPushButton("Show / Hide")
        show_btn.setCheckable(True)
        show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        show_btn.setStyleSheet("""
            QPushButton { background:#374151; color:#9ca3af; border:none;
                border-radius:4px; padding:4px 12px; font-size:12px; }
            QPushButton:hover { background:#4b5563; color:#e5e7eb; }
        """)
        show_btn.toggled.connect(
            lambda on: self._key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("""
            QPushButton { background:#374151; color:#e5e7eb; border:none;
                border-radius:4px; padding:7px 18px; font-size:13px; }
            QPushButton:hover { background:#4b5563; }
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save_btn = QPushButton("Save Key")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton { background:#4f46e5; color:white; border:none;
                border-radius:4px; padding:7px 18px; font-size:13px; }
            QPushButton:hover { background:#4338ca; }
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _save(self) -> None:
        style_store.save_openai_key(self._key_input.text().strip())
        self.accept()
