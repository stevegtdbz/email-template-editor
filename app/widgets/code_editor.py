"""
CodeEditor  — container widget with:
  • _CodeEdit  — QPlainTextEdit with line numbers, fold markers, HTML syntax highlight
  • _FindBar   — Ctrl+F find bar (Escape to close)
  • Toolbar    — Format Document button (Ctrl+Shift+F)
"""
from __future__ import annotations

import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel, QPushButton, QLineEdit,
)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPolygon, QSyntaxHighlighter, QTextCharFormat,
    QTextCursor, QTextDocument, QTextFormat, QKeySequence, QShortcut,
)


# ── Constants ─────────────────────────────────────────────────────────────────

_VOID = frozenset([
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
])

_FOLD_W = 16   # px reserved on right side of gutter for fold triangles


# ── HTML formatter ─────────────────────────────────────────────────────────────

def _format_html(src: str) -> str:
    """Reformat HTML with 2-space indentation (no extra dependencies)."""
    # Split on tag boundaries; keep style/script blocks intact
    TOKEN = re.compile(
        r'(<!--.*?-->|<!\[CDATA\[.*?\]\]>|<!DOCTYPE[^>]*>'
        r'|<style(?:\s[^>]*)?>.*?</style>'
        r'|<script(?:\s[^>]*)?>.*?</script>'
        r'|<[^>]+>)',
        re.DOTALL | re.IGNORECASE,
    )
    pad   = '  '
    depth = 0
    out: list[str] = []

    for tok in re.split(TOKEN, src):
        s = tok.strip()
        if not s:
            continue
        if s.startswith('<!--') or re.match(r'<!\[', s, re.I):
            out.append(pad * depth + s)
        elif re.match(r'<!DOCTYPE', s, re.I):
            out.append(s)
        elif re.match(r'<(style|script)', s, re.I):
            out.append(pad * depth + s)
        elif s.startswith('</'):
            depth = max(0, depth - 1)
            out.append(pad * depth + s)
        elif s.startswith('<'):
            m = re.match(r'<([a-zA-Z][a-zA-Z0-9_\-:.]*)', s)
            tag = m.group(1).lower() if m else ''
            out.append(pad * depth + s)
            if tag and tag not in _VOID and not s.rstrip().endswith('/>'):
                depth += 1
        else:
            text = ' '.join(s.split())
            if text:
                out.append(pad * depth + text)
    return '\n'.join(out)


# ── Syntax highlighter ─────────────────────────────────────────────────────────

class HtmlHighlighter(QSyntaxHighlighter):
    """VS Code Dark+-inspired colours for HTML."""

    def __init__(self, document):
        super().__init__(document)

        def fmt(color: str, italic=False, bold=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if italic: f.setFontItalic(True)
            if bold:   f.setFontWeight(700)
            return f

        self._rules = [
            (re.compile(r'<!DOCTYPE[^>]*>', re.I), fmt('#808080')),
            (re.compile(r'</?[\w\-:.]+'),           fmt('#569cd6')),
            (re.compile(r'\b[\w\-:.]+(?=\s*=)'),    fmt('#9cdcfe')),
            (re.compile(r'"[^"]*"'),                 fmt('#ce9178')),
            (re.compile(r"'[^']*'"),                 fmt('#ce9178')),
            (re.compile(r'[<>/=]'),                  fmt('#808080')),
            (re.compile(r'#[0-9a-fA-F]{3,8}'),      fmt('#c586c0')),
            (re.compile(r'\b[\w\-]+(?=\s*:)'),       fmt('#9cdcfe')),
            (re.compile(r'\{\{[^}]+\}\}'),           fmt('#dcdcaa', bold=True)),
        ]
        self._comment_fmt   = fmt('#6a9955', italic=True)
        self._comment_start = re.compile(r'<!--')
        self._comment_end   = re.compile(r'-->')

    def highlightBlock(self, text: str) -> None:
        self.setCurrentBlockState(0)
        start = 0 if self.previousBlockState() == 1 else -1

        if self.previousBlockState() != 1:
            m = self._comment_start.search(text)
            start = m.start() if m else -1

        while start >= 0:
            m_end = self._comment_end.search(text, start)
            if m_end:
                self.setFormat(start, m_end.end() - start, self._comment_fmt)
                m_next = self._comment_start.search(text, m_end.end())
                start  = m_next.start() if m_next else -1
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self._comment_fmt)
                break

        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                if self.format(m.start()).foreground().color() == QColor('#6a9955'):
                    continue
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Gutter ─────────────────────────────────────────────────────────────────────

class _Gutter(QWidget):
    def __init__(self, editor: '_CodeEdit'):
        super().__init__(editor)
        self._ed = editor

    def sizeHint(self) -> QSize:
        return QSize(self._ed.gutter_width(), 0)

    def paintEvent(self, event):
        self._ed._paint_gutter(event)

    def mousePressEvent(self, event):
        # Fold triangle area is the rightmost _FOLD_W pixels
        if event.position().x() >= self._ed.gutter_width() - _FOLD_W:
            y     = int(event.position().y())
            block = self._ed.firstVisibleBlock()
            top   = int(self._ed.blockBoundingGeometry(block)
                        .translated(self._ed.contentOffset()).top())
            while block.isValid():
                h = int(self._ed.blockBoundingRect(block).height())
                if top <= y < top + h:
                    self._ed.toggle_fold(block)
                    return
                top  += h
                block = block.next()


# ── Inner editor ──────────────────────────────────────────────────────────────

class _CodeEdit(QPlainTextEdit):
    FONT_FAMILY  = "Monospace"
    FONT_SIZE    = 11
    BG           = QColor("#1e1f22")
    GUTTER_BG    = QColor("#1a1b1e")
    GUTTER_FG    = QColor("#4b5563")
    CURSOR_LINE  = QColor("#2a2d31")
    TEXT_COLOR   = QColor("#d4d4d4")
    FOLD_FG      = QColor("#4b6080")
    MATCH_BG     = QColor("#4a3800")
    MATCH_FG     = QColor("#fde68a")
    MATCH_CUR_BG = QColor("#b45309")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter      = _Gutter(self)
        self._highlighter = HtmlHighlighter(self.document())
        self._folds: dict[int, int] = {}          # start_block_num → end_block_num
        self._find_matches: list[QTextCursor] = []
        self._find_current = -1
        self._find_sels: list = []

        font = QFont(self.FONT_FAMILY, self.FONT_SIZE)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 2)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        pal = self.palette()
        pal.setColor(pal.ColorRole.Base, self.BG)
        pal.setColor(pal.ColorRole.Text, self.TEXT_COLOR)
        self.setPalette(pal)
        self.setStyleSheet("border:none; selection-background-color:#264f78;")

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self.document().contentsChanged.connect(self._on_contents_changed)
        self._update_gutter_width(0)
        self._refresh_extra_selections()

    # ── Content change → reset folds ─────────────────────────────────────────

    def _on_contents_changed(self) -> None:
        if self._folds:
            self._restore_all_blocks()
            self._folds.clear()
            self._gutter.update()

    def _restore_all_blocks(self) -> None:
        doc = self.document()
        for start, end in self._folds.items():
            for n in range(start + 1, end):
                b = doc.findBlockByNumber(n)
                if b.isValid():
                    b.setVisible(True)
        doc.markContentsDirty(0, doc.characterCount())
        self.viewport().update()

    # ── Folding ────────────────────────────────────────────────────────────────

    @staticmethod
    def _fold_tag(block) -> str | None:
        """Return tag name if block is a foldable opening tag, else None."""
        text = block.text()
        m = re.match(r'\s*<([a-zA-Z][a-zA-Z0-9_\-:.]*)', text)
        if not m:
            return None
        tag = m.group(1).lower()
        if tag in _VOID or '/>' in text:
            return None
        return tag

    def _find_fold_end(self, start_block) -> int | None:
        """Return block number of closing tag that matches the opening on start_block."""
        tag = self._fold_tag(start_block)
        if tag is None:
            return None
        etag  = re.escape(tag)
        depth = 0
        b     = start_block
        while b.isValid():
            t      = b.text()
            depth += len(re.findall(f'<{etag}(?=\\s|>)', t, re.I))
            depth -= len(re.findall(f'</{etag}\\s*>', t, re.I))
            if depth <= 0 and b.blockNumber() != start_block.blockNumber():
                return b.blockNumber()
            b = b.next()
        return None

    def toggle_fold(self, block) -> None:
        num = block.blockNumber()
        doc = self.document()

        if num in self._folds:
            end_num = self._folds.pop(num)
            for n in range(num + 1, end_num):
                b = doc.findBlockByNumber(n)
                if b.isValid():
                    b.setVisible(True)
        else:
            if self._fold_tag(block) is None:
                return
            end_num = self._find_fold_end(block)
            if end_num is None or end_num <= num:
                return
            self._folds[num] = end_num
            for n in range(num + 1, end_num):
                b = doc.findBlockByNumber(n)
                if b.isValid():
                    b.setVisible(False)

        doc.markContentsDirty(0, doc.characterCount())
        self._gutter.update()
        self.viewport().update()

    # ── Find ──────────────────────────────────────────────────────────────────

    def search(self, query: str) -> int:
        self._find_matches.clear()
        self._find_current = -1
        if query:
            doc    = self.document()
            cursor = QTextCursor(doc)
            while True:
                found = doc.find(query, cursor)
                if found.isNull():
                    break
                self._find_matches.append(QTextCursor(found))
                cursor = found
            if self._find_matches:
                self._find_current = 0
                self._jump_to(0)
        self._refresh_extra_selections()
        return len(self._find_matches)

    def find_next(self) -> None:
        if not self._find_matches:
            return
        self._find_current = (self._find_current + 1) % len(self._find_matches)
        self._jump_to(self._find_current)

    def find_prev(self) -> None:
        if not self._find_matches:
            return
        self._find_current = (self._find_current - 1) % len(self._find_matches)
        self._jump_to(self._find_current)

    def clear_search(self) -> None:
        self._find_matches.clear()
        self._find_current = -1
        self._refresh_extra_selections()

    def _jump_to(self, idx: int) -> None:
        c = self._find_matches[idx]
        self.setTextCursor(c)
        self.ensureCursorVisible()
        self._refresh_extra_selections()

    # ── Extra selections (current-line + find highlights) ────────────────────

    def _refresh_extra_selections(self) -> None:
        from PyQt6.QtWidgets import QTextEdit
        sels = []

        # Current line
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.CURSOR_LINE)
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        sels.append(sel)

        # Find matches
        for i, c in enumerate(self._find_matches):
            s = QTextEdit.ExtraSelection()
            if i == self._find_current:
                s.format.setBackground(self.MATCH_CUR_BG)
                s.format.setForeground(QColor("#ffffff"))
            else:
                s.format.setBackground(self.MATCH_BG)
                s.format.setForeground(self.MATCH_FG)
            s.cursor = c
            sels.append(s)

        self.setExtraSelections(sels)

    # ── Gutter ─────────────────────────────────────────────────────────────────

    def gutter_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return _FOLD_W + 8 + self.fontMetrics().horizontalAdvance('9') * (digits + 1)

    def _update_gutter_width(self, _) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(
            QRect(cr.left(), cr.top(), self.gutter_width(), cr.height())
        )

    def _paint_gutter(self, event) -> None:
        painter  = QPainter(self._gutter)
        gw       = self._gutter.width()
        num_right = gw - _FOLD_W - 4
        fold_cx  = gw - _FOLD_W // 2

        painter.fillRect(event.rect(), self.GUTTER_BG)

        block  = self.firstVisibleBlock()
        num    = block.blockNumber()
        top    = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        h      = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # Line number
                painter.setPen(self.GUTTER_FG)
                painter.drawText(0, top, num_right, h,
                                 Qt.AlignmentFlag.AlignRight, str(num + 1))

                # Fold marker
                mid_y = top + h // 2
                tag   = self._fold_tag(block)
                if tag is not None:
                    folded = num in self._folds
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(self.FOLD_FG)
                    if folded:
                        # ▶ right-pointing triangle
                        poly = QPolygon([
                            QPoint(fold_cx - 4, mid_y - 5),
                            QPoint(fold_cx - 4, mid_y + 5),
                            QPoint(fold_cx + 4, mid_y),
                        ])
                    else:
                        # ▼ down-pointing triangle
                        poly = QPolygon([
                            QPoint(fold_cx - 5, mid_y - 3),
                            QPoint(fold_cx + 5, mid_y - 3),
                            QPoint(fold_cx,     mid_y + 4),
                        ])
                    painter.drawPolygon(poly)

            block  = block.next()
            top    = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num   += 1


# ── Find bar ──────────────────────────────────────────────────────────────────

_BTN_SS = """
    QPushButton {
        background:#2d2f34; color:#9ca3af;
        border:1px solid #3c3f41; border-radius:3px;
        font-size:12px;
    }
    QPushButton:hover   { background:#3f4147; color:#e5e7eb; border-color:#6b7280; }
    QPushButton:pressed { background:#4b5563; }
"""


class _FindBar(QWidget):
    def __init__(self, edit: _CodeEdit, parent=None):
        super().__init__(parent)
        self._edit = edit
        self.setFixedHeight(36)
        self.setStyleSheet("background:#25272b; border-top:1px solid #3c3f41;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(5)

        self._inp = QLineEdit()
        self._inp.setPlaceholderText("Find…  (Enter = next · Shift+Enter = prev · Esc = close)")
        self._inp.setStyleSheet(
            "QLineEdit { background:#1a1b1e; color:#e5e7eb;"
            " border:1px solid #3c3f41; border-radius:3px;"
            " padding:2px 7px; font-size:12px; }"
            "QLineEdit:focus { border-color:#4f46e5; }"
        )
        self._inp.textChanged.connect(self._on_text_changed)
        self._inp.returnPressed.connect(self._on_enter)
        lay.addWidget(self._inp, 1)

        self._count = QLabel("")
        self._count.setFixedWidth(72)
        self._count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count.setStyleSheet("color:#6b7280; font-size:11px;")
        lay.addWidget(self._count)

        prev_btn = QPushButton("↑")
        prev_btn.setFixedSize(26, 26)
        prev_btn.setStyleSheet(_BTN_SS)
        prev_btn.setToolTip("Previous match  (Shift+Enter)")
        prev_btn.clicked.connect(self._prev)
        lay.addWidget(prev_btn)

        next_btn = QPushButton("↓")
        next_btn.setFixedSize(26, 26)
        next_btn.setStyleSheet(_BTN_SS)
        next_btn.setToolTip("Next match  (Enter)")
        next_btn.clicked.connect(self._next)
        lay.addWidget(next_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet(_BTN_SS)
        close_btn.setToolTip("Close  (Esc)")
        close_btn.clicked.connect(self.close_bar)
        lay.addWidget(close_btn)

    def open(self) -> None:
        self.setVisible(True)
        self._inp.setFocus()
        self._inp.selectAll()
        # Re-run search with existing text
        self._on_text_changed(self._inp.text())

    def close_bar(self) -> None:
        self.setVisible(False)
        self._edit.clear_search()
        self._count.setText("")
        self._edit.setFocus()

    def _on_text_changed(self, text: str) -> None:
        n = self._edit.search(text)
        if not text:
            self._count.setText("")
            self._count.setStyleSheet("color:#6b7280; font-size:11px;")
        elif n == 0:
            self._count.setText("No matches")
            self._count.setStyleSheet("color:#f87171; font-size:11px;")
        else:
            self._update_count()

    def _update_count(self) -> None:
        n   = len(self._edit._find_matches)
        idx = self._edit._find_current + 1
        self._count.setText(f"{idx} / {n}")
        self._count.setStyleSheet("color:#6b7280; font-size:11px;")

    def _on_enter(self) -> None:
        from PyQt6.QtWidgets import QApplication
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._prev()
        else:
            self._next()

    def _next(self) -> None:
        self._edit.find_next()
        self._update_count()

    def _prev(self) -> None:
        self._edit.find_prev()
        self._update_count()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
        else:
            super().keyPressEvent(event)


# ── Public CodeEditor container ────────────────────────────────────────────────

class CodeEditor(QWidget):
    """
    Public API (mirrors QPlainTextEdit subset used by preview.py):
      setPlainText(text) / toPlainText() / document()

    Keyboard shortcuts:
      Ctrl+F        → open find bar
      Ctrl+Shift+F  → format HTML document
      Esc           → close find bar (when focused)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#1e1f22;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ────────────────────────────────────────────────────────────
        tb = QWidget()
        tb.setFixedHeight(30)
        tb.setStyleSheet("background:#25272b; border-bottom:1px solid #2d2f34;")
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(8, 2, 8, 2)
        tbl.setSpacing(6)

        fmt_btn = QPushButton("⟳  Format HTML")
        fmt_btn.setFixedHeight(24)
        fmt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fmt_btn.setToolTip("Format / prettify HTML document  (Ctrl+Shift+F)")
        fmt_btn.setStyleSheet("""
            QPushButton {
                background:#2d2f34; color:#9ca3af;
                border:1px solid #3c3f41; border-radius:3px;
                padding:0 12px; font-size:11px;
            }
            QPushButton:hover   { background:#3f4147; color:#e5e7eb; border-color:#4f46e5; }
            QPushButton:pressed { background:#4f46e5; color:white; }
        """)
        fmt_btn.clicked.connect(self._format)
        tbl.addWidget(fmt_btn)
        tbl.addStretch()

        hint = QLabel("Ctrl+F  find  ·  click ▼ in gutter to fold")
        hint.setStyleSheet("color:#3c3f41; font-size:10px;")
        tbl.addWidget(hint)

        root.addWidget(tb)

        # ── Inner editor ───────────────────────────────────────────────────────
        self._edit = _CodeEdit(self)
        root.addWidget(self._edit, 1)

        # ── Find bar ───────────────────────────────────────────────────────────
        self._find_bar = _FindBar(self._edit, self)
        self._find_bar.setVisible(False)
        root.addWidget(self._find_bar)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+F"),       self).activated.connect(self._find_bar.open)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self).activated.connect(self._format)

    # ── Forwarded API ──────────────────────────────────────────────────────────

    def setPlainText(self, text: str) -> None:
        self._edit.setPlainText(text)

    def toPlainText(self) -> str:
        return self._edit.toPlainText()

    def document(self):
        return self._edit.document()

    # ── Format ─────────────────────────────────────────────────────────────────

    def _format(self) -> None:
        src = self._edit.toPlainText()
        if not src.strip():
            return
        try:
            formatted = _format_html(src)
        except Exception:
            return
        cursor = self._edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(formatted)
        self._edit.moveCursor(QTextCursor.MoveOperation.Start)
