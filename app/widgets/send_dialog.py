from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QWidget, QFrame,
)
from PyQt6.QtCore import Qt
from app import styles
from app.email_sender import (
    SmtpConfig, SendWorker, OUTLOOK_AVAILABLE,
    load_last_to, save_last_to,
    load_last_via, save_last_via,
)
from app.widgets.smtp_settings_dialog import SmtpSettingsDialog
from app.widgets.multi_email_input import MultiEmailInput


class SendDialog(QDialog):
    def __init__(self, source_path: Path, parent=None):
        super().__init__(parent)
        self._source_path = source_path
        self._config      = SmtpConfig.load()
        self._worker: SendWorker | None = None

        self.setWindowTitle(f"Send  ·  {source_path.name}")
        self.setFixedWidth(560)
        self.setStyleSheet(f"background:{styles.BG_MID}; color:#e5e7eb;")
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Title + file chip
        title_row = QHBoxLayout()
        title = QLabel("Send Template Email")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#e5e7eb;")
        title_row.addWidget(title)
        title_row.addStretch()
        chip = QLabel(self._source_path.name)
        chip.setStyleSheet(
            "background:#1e3a5f; color:#93c5fd; font-size:11px;"
            " border-radius:4px; padding:3px 8px;"
        )
        title_row.addWidget(chip)
        root.addLayout(title_row)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#3c3f41;")
        root.addWidget(line)

        # ── Recipients (chip inputs) ──────────────────────────────────────────
        lbl_style = "color:#9ca3af; font-size:12px; font-weight:bold; letter-spacing:.5px;"

        to_lbl = QLabel("TO")
        to_lbl.setStyleSheet(lbl_style)
        root.addWidget(to_lbl)

        self._to = MultiEmailInput("recipient@example.com — press Enter or comma to add")
        self._to.set_from_text(load_last_to())
        root.addWidget(self._to)

        cc_lbl = QLabel("CC  (optional)")
        cc_lbl.setStyleSheet(lbl_style)
        root.addWidget(cc_lbl)

        self._cc = MultiEmailInput("cc@example.com")
        root.addWidget(self._cc)

        # ── Subject ───────────────────────────────────────────────────────────
        subj_lbl = QLabel("SUBJECT")
        subj_lbl.setStyleSheet(lbl_style)
        root.addWidget(subj_lbl)

        default_subject = (
            self._source_path.stem.replace("-", " ").replace("_", " ").title()
        )
        self._subject = QLineEdit(default_subject)
        self._subject.setStyleSheet(
            "background:#1e1f22; color:#e5e7eb; border:1px solid #3c3f41;"
            " border-radius:4px; padding:6px 10px; font-size:13px;"
        )
        root.addWidget(self._subject)

        # ── Via row ───────────────────────────────────────────────────────────
        via_row = QHBoxLayout()
        via_row.setSpacing(10)

        via_label = QLabel("Send via:")
        via_label.setStyleSheet("color:#9ca3af; font-size:13px;")
        via_row.addWidget(via_label)

        self._via = QComboBox()
        self._via.setStyleSheet("""
            QComboBox {
                background:#1e1f22; color:#e5e7eb;
                border:1px solid #3c3f41; border-radius:4px;
                padding:4px 8px; font-size:13px; min-width:130px;
            }
            QComboBox::drop-down { border:none; width:18px; }
            QComboBox QAbstractItemView {
                background:#1e2433; color:#e5e7eb;
                selection-background-color:#374151;
                border:1px solid #3c3f41;
            }
        """)
        self._via.addItem("Custom SMTP", "smtp")
        if OUTLOOK_AVAILABLE:
            self._via.addItem("Outlook (COM)", "outlook")

        # Restore last-used selection
        last_via = load_last_via()
        for i in range(self._via.count()):
            if self._via.itemData(i) == last_via:
                self._via.setCurrentIndex(i)
                break

        self._via.currentIndexChanged.connect(self._on_via_changed)
        via_row.addWidget(self._via)

        self._cfg_btn = QPushButton("Configure SMTP…")
        self._cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cfg_btn.setStyleSheet("""
            QPushButton { background:transparent; color:#93c5fd; border:none;
                font-size:12px; text-decoration:underline; }
            QPushButton:hover { color:white; }
        """)
        self._cfg_btn.clicked.connect(self._open_smtp_settings)
        via_row.addWidget(self._cfg_btn)
        via_row.addStretch()
        root.addLayout(via_row)

        # From label
        self._from_label = QLabel()
        self._from_label.setStyleSheet("color:#6b7280; font-size:11px;")
        root.addWidget(self._from_label)
        self._refresh_from_label()

        # Trigger visibility update for initial via value
        self._on_via_changed(self._via.currentIndex())

        # Status
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size:12px; color:#9ca3af;")
        root.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
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

        self._send_btn = QPushButton("Send Email")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet("""
            QPushButton { background:#059669; color:white; border:none;
                border-radius:4px; padding:7px 18px; font-size:13px; }
            QPushButton:hover    { background:#047857; }
            QPushButton:disabled { background:#374151; color:#6b7280; }
        """)
        self._send_btn.clicked.connect(self._send)
        btn_row.addWidget(self._send_btn)
        root.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_from_label(self) -> None:
        if self._config.is_configured:
            self._from_label.setText(f"From: {self._config.from_address}")
            self._from_label.setStyleSheet("font-size:11px; color:#6b7280;")
        else:
            self._from_label.setText("⚠  SMTP not configured — click 'Configure SMTP…'")
            self._from_label.setStyleSheet("font-size:11px; color:#f87171;")

    def _on_via_changed(self, _: int) -> None:
        is_smtp = self._via.currentData() == "smtp"
        self._cfg_btn.setVisible(is_smtp)
        self._from_label.setVisible(is_smtp)

    def _open_smtp_settings(self) -> None:
        dlg = SmtpSettingsDialog(parent=self)
        if dlg.exec():
            self._config = SmtpConfig.load()
            self._refresh_from_label()

    # ── Send ──────────────────────────────────────────────────────────────────

    def _send(self) -> None:
        to = self._to.get_emails()
        if not to:
            self._set_status("Please enter at least one recipient.", error=True)
            return

        method = self._via.currentData()
        if method == "smtp" and not self._config.is_configured:
            self._set_status("SMTP is not configured. Click 'Configure SMTP…' first.", error=True)
            return

        html = self._source_path.read_text(encoding="utf-8")
        cc   = self._cc.get_emails()
        n    = len(to)
        self._send_btn.setEnabled(False)
        self._send_btn.setText("Sending…")
        self._set_status(
            f"Sending to {n} recipient{'s' if n != 1 else ''}…", error=False
        )

        self._worker = SendWorker(
            method    = method,
            html_body = html,
            to        = to,
            subject   = self._subject.text().strip(),
            cc        = cc,
            config    = self._config if method == "smtp" else None,
            parent    = self,
        )
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_success(self) -> None:
        save_last_to(self._to.get_text())
        save_last_via(self._via.currentData())
        n = len(self._to.get_emails())
        self._set_status(
            f"Sent to {n} recipient{'s' if n != 1 else ''} ✓",
            error=False, color="#34d399",
        )
        self._send_btn.setText("Sent ✓")

    def _on_error(self, msg: str) -> None:
        self._send_btn.setEnabled(True)
        self._send_btn.setText("Send Email")
        self._set_status(f"Error: {msg}", error=True)

    def _set_status(self, text: str, *, error: bool, color: str = "") -> None:
        c = color or ("#f87171" if error else "#9ca3af")
        self._status.setStyleSheet(f"font-size:12px; color:{c};")
        self._status.setText(text)
