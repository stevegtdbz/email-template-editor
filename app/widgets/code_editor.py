"""
CodeEditor  — QPlainTextEdit with line numbers + HTML syntax highlighting.
HtmlHighlighter — regex-based, handles multi-line comments.
"""
from __future__ import annotations

import re
from PyQt6.QtWidgets import QPlainTextEdit, QWidget
from PyQt6.QtCore    import Qt, QRect, QSize
from PyQt6.QtGui     import (
    QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat,
)

# ── Syntax highlighter ────────────────────────────────────────────────────────

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

        # Order matters — later rules overwrite earlier ones in the same span.
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = [
            # DOCTYPE / XML declaration
            (re.compile(r'<!DOCTYPE[^>]*>', re.I), fmt('#808080')),
            # Opening/closing tag names  <div  </div
            (re.compile(r'</?[\w\-:.]+'),           fmt('#569cd6')),
            # Attribute names  class=  href=
            (re.compile(r'\b[\w\-:.]+(?=\s*=)'),    fmt('#9cdcfe')),
            # Quoted attribute values
            (re.compile(r'"[^"]*"'),                 fmt('#ce9178')),
            (re.compile(r"'[^']*'"),                 fmt('#ce9178')),
            # Standalone punctuation  < > / =
            (re.compile(r'[<>/=]'),                  fmt('#808080')),
            # Hex colours inside style="" values
            (re.compile(r'#[0-9a-fA-F]{3,8}'),      fmt('#c586c0')),
            # CSS property names inside style=""
            (re.compile(r'\b[\w\-]+(?=\s*:)'),       fmt('#9cdcfe')),
            # Template variables  {{var}}
            (re.compile(r'\{\{[^}]+\}\}'),           fmt('#dcdcaa', bold=True)),
        ]

        self._comment_fmt   = fmt('#6a9955', italic=True)
        self._comment_start = re.compile(r'<!--')
        self._comment_end   = re.compile(r'-->')

    def highlightBlock(self, text: str) -> None:
        # ── multi-line comments ───────────────────────────────────────────────
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
                start = m_next.start() if m_next else -1
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self._comment_fmt)
                break

        # ── inline rules (skip regions already formatted as comment) ──────────
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                if self.format(m.start()).foreground().color() == QColor('#6a9955'):
                    continue  # inside a comment
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Line-number gutter ────────────────────────────────────────────────────────

class _Gutter(QWidget):
    def __init__(self, editor: CodeEditor):
        super().__init__(editor)
        self._ed = editor

    def sizeHint(self) -> QSize:
        return QSize(self._ed.gutter_width(), 0)

    def paintEvent(self, event):
        self._ed._paint_gutter(event)


# ── Code editor ───────────────────────────────────────────────────────────────

class CodeEditor(QPlainTextEdit):
    FONT_FAMILY = "Monospace"
    FONT_SIZE   = 11

    BG         = QColor("#1e1f22")
    GUTTER_BG  = QColor("#1a1b1e")
    GUTTER_FG  = QColor("#4b5563")
    CURSOR_LINE = QColor("#2a2d31")
    TEXT_COLOR  = QColor("#d4d4d4")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _Gutter(self)
        self._highlighter = HtmlHighlighter(self.document())

        font = QFont(self.FONT_FAMILY, self.FONT_SIZE)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(' ') * 2
        )
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        palette = self.palette()
        palette.setColor(palette.ColorRole.Base,  self.BG)
        palette.setColor(palette.ColorRole.Text,  self.TEXT_COLOR)
        self.setPalette(palette)
        self.setStyleSheet("border:none; selection-background-color:#264f78;")

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_gutter_width(0)
        self._highlight_current_line()

    # ── Gutter ────────────────────────────────────────────────────────────────

    def gutter_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 6 + self.fontMetrics().horizontalAdvance('9') * (digits + 1)

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
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), self.GUTTER_BG)

        block  = self.firstVisibleBlock()
        num    = block.blockNumber()
        top    = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        h      = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(self.GUTTER_FG)
                painter.drawText(
                    0, top, self._gutter.width() - 6, h,
                    Qt.AlignmentFlag.AlignRight,
                    str(num + 1),
                )
            block  = block.next()
            top    = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num   += 1

    # ── Current-line highlight ────────────────────────────────────────────────

    def _highlight_current_line(self) -> None:
        from PyQt6.QtWidgets import QTextEdit
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(self.CURSOR_LINE)
        sel.format.setProperty(
            QTextFormat.Property.FullWidthSelection, True  # type: ignore[attr-defined]
        )
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])


# fix missing import used in _highlight_current_line
from PyQt6.QtGui import QTextFormat  # noqa: E402  (used above via string ref)
