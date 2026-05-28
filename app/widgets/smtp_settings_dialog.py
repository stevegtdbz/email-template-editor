from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app import styles
from app.email_sender import SmtpConfig, test_smtp


class _TestWorker(QThread):
    done = pyqtSignal(str)  # "" = success, else error message

    def __init__(self, config: SmtpConfig, parent=None):
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        self.done.emit(test_smtp(self._config))


class SmtpSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SMTP Configuration")
        self.setFixedWidth(480)
        self.setStyleSheet(f"background:{styles.BG_MID}; color:#e5e7eb;")
        self._config = SmtpConfig.load()
        self._worker: _TestWorker | None = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("SMTP Configuration")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#e5e7eb;")
        root.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        field_style = (
            f"background:#1e1f22; color:#e5e7eb; border:1px solid #3c3f41;"
            f" border-radius:4px; padding:5px 8px; font-size:13px;"
        )

        self._host = QLineEdit(self._config.host)
        self._host.setPlaceholderText("smtp.gmail.com")
        self._host.setStyleSheet(field_style)
        form.addRow("Host:", self._host)

        port_row = QWidget()
        port_row_layout = QHBoxLayout(port_row)
        port_row_layout.setContentsMargins(0, 0, 0, 0)
        port_row_layout.setSpacing(12)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(self._config.port)
        self._port.setStyleSheet(field_style + " max-width:80px;")
        port_row_layout.addWidget(self._port)

        self._tls = QCheckBox("STARTTLS")
        self._tls.setChecked(self._config.use_tls)
        self._tls.setStyleSheet("color:#9ca3af; font-size:13px;")
        port_row_layout.addWidget(self._tls)
        port_row_layout.addStretch()
        form.addRow("Port:", port_row)

        self._user = QLineEdit(self._config.username)
        self._user.setPlaceholderText("user@example.com")
        self._user.setStyleSheet(field_style)
        form.addRow("Username:", self._user)

        self._password = QLineEdit(self._config.password)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("••••••••")
        self._password.setStyleSheet(field_style)
        form.addRow("Password:", self._password)

        self._from_name = QLineEdit(self._config.from_name)
        self._from_name.setPlaceholderText("Acme Team  (optional)")
        self._from_name.setStyleSheet(field_style)
        form.addRow("From name:", self._from_name)

        root.addLayout(form)

        # Status label
        self._status = QLabel("")
        self._status.setStyleSheet("font-size:12px; color:#9ca3af;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet("""
            QPushButton { background:#374151; color:#e5e7eb; border:none;
                border-radius:4px; padding:7px 16px; font-size:13px; }
            QPushButton:hover    { background:#4b5563; }
            QPushButton:disabled { color:#6b7280; }
        """)
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)
        btn_row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("""
            QPushButton { background:#374151; color:#e5e7eb; border:none;
                border-radius:4px; padding:7px 16px; font-size:13px; }
            QPushButton:hover { background:#4b5563; }
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Save")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet("""
            QPushButton { background:#4f46e5; color:white; border:none;
                border-radius:4px; padding:7px 16px; font-size:13px; }
            QPushButton:hover { background:#4338ca; }
        """)
        save.clicked.connect(self._save)
        btn_row.addWidget(save)

        root.addLayout(btn_row)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _build_config(self) -> SmtpConfig:
        return SmtpConfig(
            host      = self._host.text().strip(),
            port      = self._port.value(),
            username  = self._user.text().strip(),
            password  = self._password.text(),
            from_name = self._from_name.text().strip(),
            use_tls   = self._tls.isChecked(),
        )

    def _test_connection(self) -> None:
        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing…")
        self._status.setStyleSheet("font-size:12px; color:#9ca3af;")
        self._status.setText("Connecting…")
        self._worker = _TestWorker(self._build_config(), parent=self)
        self._worker.done.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, error: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("Test Connection")
        if error:
            self._status.setStyleSheet("font-size:12px; color:#f87171;")
            self._status.setText(f"Failed: {error}")
        else:
            self._status.setStyleSheet("font-size:12px; color:#34d399;")
            self._status.setText("Connection successful ✓")

    def _save(self) -> None:
        cfg = self._build_config()
        cfg.save()
        self.accept()

    def get_config(self) -> SmtpConfig:
        return self._build_config()
