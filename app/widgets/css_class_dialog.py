from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPlainTextEdit, QDialogButtonBox,
    QPushButton, QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from app import styles

_FIELD_SS = """
    QLineEdit, QPlainTextEdit {
        background:#1a1b1e; color:#e5e7eb;
        border:1px solid #3c3f41; border-radius:4px;
        font-size:12px; font-family:monospace; padding:4px 6px;
        selection-background-color:#4f46e5;
    }
    QLineEdit:focus, QPlainTextEdit:focus { border-color:#4f46e5; }
"""


class _MediaRuleRow(QWidget):
    remove_requested = pyqtSignal()

    def __init__(self, query: str = "", css: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:#222326; border-radius:4px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        # Query row: @media ( <input> )  [✕]
        q_row = QHBoxLayout()
        q_row.setSpacing(4)

        for txt in ("@media (", ):
            lbl = QLabel(txt)
            lbl.setStyleSheet("color:#6b7280; font-size:12px; font-family:monospace;")
            q_row.addWidget(lbl)

        self._query = QLineEdit(query)
        self._query.setPlaceholderText("max-width: 600px")
        self._query.setStyleSheet(_FIELD_SS)
        q_row.addWidget(self._query, 1)

        lbl2 = QLabel(")")
        lbl2.setStyleSheet("color:#6b7280; font-size:12px; font-family:monospace;")
        q_row.addWidget(lbl2)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(20, 20)
        rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rm_btn.setToolTip("Remove rule")
        rm_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6b7280;border:none;font-size:11px;}"
            "QPushButton:hover{color:#f87171;}"
        )
        rm_btn.clicked.connect(self.remove_requested)
        q_row.addWidget(rm_btn)
        layout.addLayout(q_row)

        self._css = QPlainTextEdit(css)
        self._css.setPlaceholderText("CSS properties for this breakpoint…")
        self._css.setMinimumHeight(50)
        self._css.setMaximumHeight(80)
        self._css.setStyleSheet(_FIELD_SS)
        layout.addWidget(self._css)

    @property
    def query(self) -> str:
        return self._query.text().strip()

    @property
    def css(self) -> str:
        return self._css.toPlainText().strip()


class CssClassDialog(QDialog):
    """Add or edit a CSS class with optional @media query rules."""

    def __init__(
        self,
        name: str = "",
        css: str = "",
        media: list | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("CSS Class")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background:{styles.BG_MID}; }}
            QLabel  {{ color:{styles.TEXT_MUTED}; font-size:13px; }}
        """)

        self._media_rows: list[_MediaRuleRow] = []

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        # ── Base class fields ─────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText("e.g. hero-title")
        self._name_edit.setStyleSheet(
            f"background:{styles.BG_DARK}; color:#e5e7eb; border:1px solid #3c3f41;"
            "border-radius:4px; font-size:13px; padding:5px 8px;"
            "selection-background-color:#4f46e5;"
        )
        form.addRow("Class name:", self._name_edit)

        self._css_edit = QPlainTextEdit(css)
        self._css_edit.setPlaceholderText("e.g. font-size: 34px; font-family: Arial;")
        self._css_edit.setMinimumHeight(70)
        self._css_edit.setMaximumHeight(120)
        self._css_edit.setStyleSheet(
            f"background:{styles.BG_DARK}; color:#e5e7eb; border:1px solid #3c3f41;"
            "border-radius:4px; font-size:13px; font-family:monospace; padding:5px 8px;"
            "selection-background-color:#4f46e5;"
        )
        form.addRow("CSS:", self._css_edit)

        root.addLayout(form)

        # ── Divider ───────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#3c3f41;")
        root.addWidget(line)

        # ── Media queries section ─────────────────────────────────────────────
        mq_hdr = QHBoxLayout()
        mq_lbl = QLabel("MEDIA QUERIES")
        mq_lbl.setStyleSheet(
            "color:#4b5563; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        mq_hdr.addWidget(mq_lbl)
        mq_hdr.addStretch()

        add_btn = QPushButton("+ Add Rule")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background:#2d2f34; color:#a5b4fc; border:1px solid #3c3f41;
                border-radius:3px; padding:2px 10px; font-size:11px;
            }
            QPushButton:hover   { background:#3f4147; border-color:#4f46e5; }
            QPushButton:pressed { background:#4f46e5; color:white; }
        """)
        add_btn.clicked.connect(lambda: self._add_media_row())
        mq_hdr.addWidget(add_btn)
        root.addLayout(mq_hdr)

        # Scrollable rule list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(260)
        scroll.setMinimumHeight(60)
        scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid #3c3f41; border-radius:4px;"
            f"background:{styles.BG_DARK};}}"
            f"QScrollBar:vertical{{background:{styles.BG_DARK};width:6px;border:none;}}"
            "QScrollBar::handle:vertical{background:#3c3f41;border-radius:3px;min-height:16px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        self._media_body = QWidget()
        self._media_body.setStyleSheet(f"background:{styles.BG_DARK};")
        self._media_layout = QVBoxLayout(self._media_body)
        self._media_layout.setContentsMargins(8, 8, 8, 8)
        self._media_layout.setSpacing(8)
        self._media_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._no_rules_lbl = QLabel("No media rules — click + Add Rule")
        self._no_rules_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_rules_lbl.setStyleSheet(
            "color:#4b5563; font-size:11px; font-style:italic;"
        )
        self._media_layout.addWidget(self._no_rules_lbl)

        scroll.setWidget(self._media_body)
        root.addWidget(scroll)

        # Pre-populate
        for m in (media or []):
            self._add_media_row(m.get("query", ""), m.get("css", ""))

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Save).setStyleSheet("""
            QPushButton { background:#4f46e5; color:white; border:none;
                border-radius:4px; padding:5px 18px; font-size:13px; }
            QPushButton:hover { background:#4338ca; }
        """)
        btns.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet("""
            QPushButton { background:#374151; color:#9ca3af; border:none;
                border-radius:4px; padding:5px 18px; font-size:13px; }
            QPushButton:hover { background:#4b5563; color:#e5e7eb; }
        """)
        root.addWidget(btns)

    # ── Media row management ──────────────────────────────────────────────────

    def _add_media_row(self, query: str = "", css: str = "") -> None:
        self._no_rules_lbl.setVisible(False)
        row = _MediaRuleRow(query, css, parent=self._media_body)
        row.remove_requested.connect(lambda: self._remove_media_row(row))
        self._media_rows.append(row)
        self._media_layout.addWidget(row)

    def _remove_media_row(self, row: _MediaRuleRow) -> None:
        if row in self._media_rows:
            self._media_rows.remove(row)
        self._media_layout.removeWidget(row)
        row.deleteLater()
        self._no_rules_lbl.setVisible(not self._media_rows)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def class_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def class_css(self) -> str:
        return self._css_edit.toPlainText().strip()

    @property
    def media_rules(self) -> list[dict]:
        return [
            {"query": r.query, "css": r.css}
            for r in self._media_rows
            if r.query
        ]
