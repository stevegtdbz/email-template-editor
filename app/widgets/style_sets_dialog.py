from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QPlainTextEdit, QDialogButtonBox,
)
from app import styles


class StyleSetDialog(QDialog):
    """Add or edit a single style set or CSS class (reused for both)."""

    def __init__(
        self,
        name: str = "",
        value: str = "",
        title: str = "Style Set",
        name_label: str = "Name:",
        value_label: str = "CSS:",
        placeholder: str = "e.g. font-family:Arial;font-size:34px;color:#333;",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setStyleSheet(f"""
            QDialog       {{ background:{styles.BG_MID}; }}
            QLabel        {{ color:{styles.TEXT_MUTED}; font-size:13px; }}
            QLineEdit, QPlainTextEdit {{
                background:{styles.BG_DARK}; color:#e5e7eb;
                border:1px solid #3c3f41; border-radius:4px;
                font-size:13px; padding:4px 8px;
                selection-background-color:#4f46e5;
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{ border-color:#4f46e5; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText("e.g. myh1")
        form.addRow(name_label, self._name_edit)

        self._value_edit = QPlainTextEdit(value)
        self._value_edit.setPlaceholderText(placeholder)
        self._value_edit.setMinimumHeight(80)
        self._value_edit.setMaximumHeight(140)
        form.addRow(value_label, self._value_edit)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        save_btn = btns.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setStyleSheet("""
            QPushButton {
                background:#4f46e5; color:white; border:none;
                border-radius:4px; padding:5px 18px; font-size:13px;
            }
            QPushButton:hover { background:#4338ca; }
        """)
        cancel_btn = btns.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background:#374151; color:#9ca3af; border:none;
                border-radius:4px; padding:5px 18px; font-size:13px;
            }
            QPushButton:hover { background:#4b5563; color:#e5e7eb; }
        """)

        layout.addWidget(btns)

    @property
    def style_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def style_value(self) -> str:
        return self._value_edit.toPlainText().strip()
