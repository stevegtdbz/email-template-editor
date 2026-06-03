"""Chip-style multi-email input widget.

Press Enter, comma, or semicolon to confirm an address as a chip.
Click × on a chip to remove it.
Paste a newline-separated list and every line becomes a chip.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, QSize, QPoint
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


# ── Minimal wrapping flow layout ──────────────────────────────────────────────

class _FlowLayout(QLayout):
    """Left-to-right, wraps to next line when width is exceeded."""

    _H = 4   # horizontal gap
    _V = 4   # vertical gap

    def __init__(self):
        super().__init__()
        self._items: list = []

    # ── Required QLayout interface ────────────────────────────────────────────

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    # ── Geometry ──────────────────────────────────────────────────────────────

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, dry_run=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        if not self._items:
            return QSize(0, 0)
        w = max(i.sizeHint().width() for i in self._items)
        h = max(i.sizeHint().height() for i in self._items)
        m = self.contentsMargins()
        return QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

    def _arrange(self, rect: QRect, dry_run: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_h = r.x(), r.y(), 0

        for item in self._items:
            sh = item.sizeHint()
            # wrap if this item would exceed the right edge (and we're not at row start)
            if x > r.x() and x + sh.width() > r.right() + 1:
                x = r.x()
                y += row_h + self._V
                row_h = 0
            if not dry_run:
                item.setGeometry(QRect(QPoint(x, y), sh))
            x += sh.width() + self._H
            row_h = max(row_h, sh.height())

        return y + row_h - rect.y() + m.bottom()


# ── Chip ──────────────────────────────────────────────────────────────────────

def _make_chip(email: str, on_remove) -> QWidget:
    chip = QWidget()
    chip.setObjectName("EmailChip")
    chip.setStyleSheet(
        "#EmailChip { background:#1e3a5f; border:1px solid #2563eb; border-radius:3px; }"
    )
    row = QHBoxLayout(chip)
    row.setContentsMargins(7, 3, 4, 3)
    row.setSpacing(5)

    lbl = QLabel(email)
    lbl.setStyleSheet("color:#93c5fd; font-size:12px; background:transparent; border:none;")
    row.addWidget(lbl)

    x = QPushButton("×")
    x.setFixedSize(14, 14)
    x.setCursor(Qt.CursorShape.PointingHandCursor)
    x.setStyleSheet(
        "QPushButton{background:transparent;color:#6b7280;border:none;"
        "font-size:12px;padding:0;}"
        "QPushButton:hover{color:#f87171;background:transparent;}"
    )
    x.clicked.connect(on_remove)
    row.addWidget(x)
    return chip


# ── Entry with paste support ──────────────────────────────────────────────────

class _EntryEdit(QLineEdit):
    """QLineEdit that splits multi-line clipboard pastes."""

    def __init__(self, on_add_emails, placeholder: str):
        super().__init__()
        self._on_add = on_add_emails
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(
            "background:transparent; color:#e5e7eb; border:none; font-size:13px;"
        )

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            text = QApplication.clipboard().text()
            if "\n" in text:
                # Multi-line paste — consume it ourselves
                emails = [
                    e.strip()
                    for line in text.splitlines()
                    for e in line.replace(";", ",").split(",")
                    if e.strip()
                ]
                self._on_add(emails)
                return
        super().keyPressEvent(event)


# ── MultiEmailInput ───────────────────────────────────────────────────────────

class MultiEmailInput(QWidget):
    """Chip-style multi-address input."""

    def __init__(self, placeholder="type address, press Enter to add…", parent=None):
        super().__init__(parent)
        self._emails: list[str] = []
        self._chip_widgets: dict[str, QWidget] = {}
        self._setup(placeholder)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _setup(self, placeholder: str) -> None:
        self.setObjectName("MEI")
        self.setStyleSheet(
            "#MEI { background:#1e1f22; border:1px solid #3c3f41; border-radius:4px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ── Chips scroll area (hidden when empty) ─────────────────────────────
        self._chips_host = QWidget()
        self._chips_host.setStyleSheet("background:transparent;")
        self._chips_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self._flow = _FlowLayout()
        self._chips_host.setLayout(self._flow)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setMaximumHeight(76)
        self._scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#1e1f22;width:5px;border:none;}"
            "QScrollBar::handle:vertical{background:#3c3f41;border-radius:2px;min-height:16px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self._scroll.setWidget(self._chips_host)
        self._scroll.setVisible(False)
        outer.addWidget(self._scroll)

        # ── Entry ─────────────────────────────────────────────────────────────
        self._entry = _EntryEdit(self._add_emails, placeholder)
        self._entry.returnPressed.connect(self._flush_entry)
        self._entry.textChanged.connect(self._on_text_changed)
        outer.addWidget(self._entry)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_text_changed(self, text: str) -> None:
        if text.endswith(",") or text.endswith(";"):
            self._flush_entry()

    def _flush_entry(self) -> None:
        raw = self._entry.text().strip().rstrip(",;").strip()
        emails = [
            e.strip()
            for e in raw.replace(";", ",").split(",")
            if e.strip()
        ]
        self._add_emails(emails)
        self._entry.clear()

    def _add_emails(self, emails: list[str]) -> None:
        for email in emails:
            if email and email not in self._emails:
                self._emails.append(email)
                chip = _make_chip(email, lambda _, e=email: self._remove(e))
                self._flow.addWidget(chip)
                self._chip_widgets[email] = chip
        self._scroll.setVisible(bool(self._emails))
        self._chips_host.updateGeometry()

    def _remove(self, email: str) -> None:
        if email not in self._emails:
            return
        self._emails.remove(email)
        chip = self._chip_widgets.pop(email, None)
        if chip:
            # Remove from flow layout
            for i in range(self._flow.count()):
                item = self._flow.itemAt(i)
                if item and item.widget() is chip:
                    self._flow.takeAt(i)
                    break
            chip.deleteLater()
        self._scroll.setVisible(bool(self._emails))
        self._chips_host.updateGeometry()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_emails(self) -> list[str]:
        """Flush the entry field and return all confirmed emails."""
        self._flush_entry()
        return list(self._emails)

    def get_text(self) -> str:
        return ", ".join(self.get_emails())

    def set_from_text(self, text: str) -> None:
        """Populate from a comma/semicolon/newline-separated string."""
        emails = [
            e.strip()
            for line in text.splitlines()
            for e in line.replace(";", ",").split(",")
            if e.strip()
        ]
        self._add_emails(emails)
