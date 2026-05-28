from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QColorDialog,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from app import styles
from app.widgets.code_editor import CodeEditor

# ── Edit mode JS ──────────────────────────────────────────────────────────────
# Injected when Edit Mode is active:
#   • Floating in-page toolbar: element tag label + ✕ Delete button
#   • Click → select element (red outline); Ctrl+Click → instant delete
#   • contentEditable for text editing anywhere
#   • Selection is tracked on mouseup/keyup so Python toolbar buttons
#     can restore it after Qt steals focus (color dialog, button clicks)
_EDIT_JS = """
(function () {
    if (window.__editModeActive) return;
    window.__editModeActive = true;

    // ── styles ───────────────────────────────────────────────────────────────
    var style = document.createElement('style');
    style.id = '__em_style__';
    style.textContent =
        '.__em_hov { outline:2px solid rgba(79,70,229,.7) !important; outline-offset:2px !important; }' +
        '.__em_sel { outline:2px solid rgba(220,38,38,.9) !important; outline-offset:2px !important; }';
    document.head.appendChild(style);

    // ── in-page delete toolbar ───────────────────────────────────────────────
    var tb = document.createElement('div');
    tb.id = '__em_tb__';
    tb.style.cssText = [
        'position:fixed;top:10px;right:10px;z-index:2147483647;',
        'background:#1e1f22;border-radius:6px;padding:6px 10px;',
        'display:flex;align-items:center;gap:10px;',
        'box-shadow:0 2px 12px rgba(0,0,0,.55);font-family:Arial,sans-serif;',
        'pointer-events:auto;user-select:none;'
    ].join('');
    var hint = document.createElement('span');
    hint.style.cssText = 'color:#6b7280;font-size:11px;';
    hint.textContent = 'Click element to select';
    tb.appendChild(hint);
    var delBtn = document.createElement('button');
    delBtn.id = '__em_del__';
    delBtn.textContent = '✕  Delete';
    delBtn.style.cssText =
        'background:#dc2626;color:white;border:none;border-radius:4px;' +
        'padding:5px 12px;font-size:12px;cursor:pointer;' +
        'opacity:.35;pointer-events:none;transition:opacity .15s;';
    tb.appendChild(delBtn);
    document.body.appendChild(tb);

    // ── element selection ────────────────────────────────────────────────────
    document.body.contentEditable = 'true';
    var selected = null;
    var lastHov  = null;

    function setSelected(el) {
        if (selected) selected.classList.remove('__em_sel');
        selected = el;
        if (selected) {
            selected.classList.add('__em_sel');
            hint.textContent = '<' + selected.tagName.toLowerCase() + '>';
            delBtn.style.opacity = '1'; delBtn.style.pointerEvents = 'auto';
        } else {
            hint.textContent = 'Click element to select';
            delBtn.style.opacity = '.35'; delBtn.style.pointerEvents = 'none';
        }
    }

    document.addEventListener('mouseover', function (e) {
        if (tb.contains(e.target)) return;
        if (lastHov && lastHov !== selected) lastHov.classList.remove('__em_hov');
        lastHov = e.target;
        if (lastHov !== selected) lastHov.classList.add('__em_hov');
    });
    document.addEventListener('mouseout', function (e) {
        if (e.target !== selected) e.target.classList.remove('__em_hov');
    });
    document.addEventListener('mousedown', function (e) {
        if (tb.contains(e.target)) return;
        var tag = e.target.tagName;
        if (tag === 'BODY' || tag === 'HTML') return;
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault(); e.stopPropagation();
            if (selected === e.target) setSelected(null);
            e.target.remove();
        } else { setSelected(e.target); }
    }, true);
    delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (selected) { selected.remove(); setSelected(null); }
    });

    // ── selection tracking for Python format toolbar ──────────────────────────
    // Saved on every mouseup / keyup so the range survives Qt focus changes
    // (color dialog, toolbar button clicks).
    function saveRange() {
        var sel = window.getSelection();
        if (sel && sel.rangeCount > 0 && !sel.isCollapsed)
            window.__savedRange = sel.getRangeAt(0).cloneRange();
    }
    document.addEventListener('mouseup', saveRange);
    document.addEventListener('keyup',   saveRange);

    window.__restoreSel = function () {
        if (!window.__savedRange) return false;
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(window.__savedRange);
        return true;
    };

    // Bold / Italic / Underline — execCommand produces <b><i><u>,
    // which are universally supported in email clients.
    window.__fmt = function (cmd) {
        window.__restoreSel();
        document.execCommand(cmd);
    };

    // Text colour — wraps selection in <span style="color:X"> for
    // maximum email-client compatibility (avoids <font color=""> fallback).
    window.__applyColor = function (hex) {
        if (!window.__restoreSel()) return;
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        var span  = document.createElement('span');
        span.style.color = hex;
        try {
            range.surroundContents(span);
        } catch (_) {
            // Selection crosses element boundaries; fall back to execCommand.
            document.execCommand('foreColor', false, hex);
        }
    };

    // Font size — wraps selection in <span style="font-size:Xpx">.
    window.__applySize = function (px) {
        if (!window.__restoreSel()) return;
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        var span  = document.createElement('span');
        span.style.fontSize = px + 'px';
        try { range.surroundContents(span); } catch (_) {}
    };

    // ── Dirty tracking ───────────────────────────────────────────────────────
    // Delayed so the toolbar/style DOM insertions above don't trip the flag.
    setTimeout(function () {
        var _obs = new MutationObserver(function () {
            document.title = '__dirty__';
        });
        _obs.observe(document.body, {
            childList: true, subtree: true,
            characterData: true, attributes: true,
        });
    }, 200);
})();
"""

# Strips edit-mode artefacts before reading outerHTML for save.
_CLEANUP_JS = """
(function () {
    var s = document.getElementById('__em_style__');  if (s)  s.remove();
    var tb = document.getElementById('__em_tb__');    if (tb) tb.remove();
    document.body.removeAttribute('contenteditable');
    document.querySelectorAll('.__em_hov,.__em_sel').forEach(function (el) {
        el.classList.remove('__em_hov', '__em_sel');
    });
    delete window.__editModeActive;
    delete window.__savedRange;
    return document.documentElement.outerHTML;
})();
"""

_BTN = """
    QPushButton {{
        background:#2d2f34; color:{fg}; border:none;
        border-radius:4px; min-width:{w}px; height:26px;
        font-size:13px; font-weight:{fw}; font-style:{fi};
        padding:0 8px;
    }}
    QPushButton:hover   {{ background:#3f4147; }}
    QPushButton:pressed {{ background:#4f46e5; color:white; }}
"""

def _fmt_btn(label: str, bold=False, italic=False, width=30) -> QPushButton:
    btn = QPushButton(label)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(_BTN.format(
        fg="white", fw="bold" if bold else "normal",
        fi="italic" if italic else "normal", w=width,
    ))
    return btn


class PreviewPane(QWidget):
    status_message  = pyqtSignal(str)
    merge_requested = pyqtSignal(Path, Path)
    send_requested  = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{styles.BG_DARK};")
        self._current_path: Path | None = None
        self._guide_path:   Path | None = None
        self._edit_mode  = False
        self._code_mode  = False
        self._dirty      = False
        self._last_color = QColor("#000000")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header_bar())
        layout.addWidget(self._build_format_bar())   # hidden until Edit Mode

        self._view = QWebEngineView()
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.page().titleChanged.connect(self._on_page_title_changed)
        layout.addWidget(self._view)

        self._code_editor = CodeEditor()
        self._code_editor.setVisible(False)
        layout.addWidget(self._code_editor)

    # ── Bar builders ──────────────────────────────────────────────────────────

    def _build_header_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background:{styles.BG_MID};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(8)

        self._title = QLabel("Select a template")
        self._title.setStyleSheet(f"color:{styles.TEXT_DIM}; font-size:12px;")
        lay.addWidget(self._title)
        lay.addStretch()

        self._merge_btn = self._action_btn("Merge with Guide", "#1e3a5f", "#93c5fd", border="#2563eb")
        self._merge_btn.setVisible(False)
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        lay.addWidget(self._merge_btn)

        self._send_btn_bar = self._action_btn("Send Email", "#065f46", "#6ee7b7", border="#059669")
        self._send_btn_bar.setVisible(False)
        self._send_btn_bar.clicked.connect(
            lambda: self.send_requested.emit(self._current_path)
        )
        lay.addWidget(self._send_btn_bar)

        self._save_btn = self._action_btn("Save", "#059669", "white")
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(self._save)
        lay.addWidget(self._save_btn)

        self._code_btn = QPushButton("< > Code")
        self._code_btn.setCheckable(True)
        self._code_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._code_btn.setStyleSheet("""
            QPushButton {
                background:#374151; color:#9ca3af; border:none;
                border-radius:4px; padding:4px 14px; font-size:12px;
                font-family: monospace;
            }
            QPushButton:checked        { background:#b45309; color:#fde68a; }
            QPushButton:hover:!checked { background:#4b5563; color:#e5e7eb; }
            QPushButton:hover:checked  { background:#92400e; }
        """)
        self._code_btn.toggled.connect(self._toggle_code_mode)
        lay.addWidget(self._code_btn)

        self._edit_btn = QPushButton("Edit Mode")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.setStyleSheet("""
            QPushButton {
                background:#374151; color:#9ca3af; border:none;
                border-radius:4px; padding:4px 14px; font-size:12px;
            }
            QPushButton:checked        { background:#4f46e5; color:white; }
            QPushButton:hover:!checked { background:#4b5563; color:#e5e7eb; }
            QPushButton:hover:checked  { background:#4338ca; }
            QPushButton:disabled       { color:#4b5563; }
        """)
        self._edit_btn.toggled.connect(self._toggle_edit_mode)
        lay.addWidget(self._edit_btn)
        return bar

    def _build_format_bar(self) -> QWidget:
        self._format_bar = QWidget()
        self._format_bar.setFixedHeight(36)
        self._format_bar.setVisible(False)
        self._format_bar.setStyleSheet(
            f"background:#25272b; border-bottom:1px solid #3c3f41;"
        )
        lay = QHBoxLayout(self._format_bar)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(4)

        # B / I / U
        b = _fmt_btn("B", bold=True)
        b.setToolTip("Bold (email-safe <b>)")
        b.clicked.connect(lambda: self._fmt("bold"))
        lay.addWidget(b)

        i = _fmt_btn("I", italic=True)
        i.setToolTip("Italic (email-safe <i>)")
        i.clicked.connect(lambda: self._fmt("italic"))
        lay.addWidget(i)

        u = _fmt_btn("U", width=30)
        u.setStyleSheet(u.styleSheet() + "QPushButton { text-decoration:underline; }")
        u.setToolTip("Underline (email-safe <u>)")
        u.clicked.connect(lambda: self._fmt("underline"))
        lay.addWidget(u)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#3c3f41;")
        sep.setFixedWidth(1)
        lay.addWidget(sep)

        # Font size
        for label, px in [("S", 12), ("M", 16), ("L", 20), ("XL", 26)]:
            btn = _fmt_btn(label, width=28)
            btn.setToolTip(f"Font size {px}px (inline style)")
            btn.clicked.connect(lambda _, p=px: self._apply_size(p))
            lay.addWidget(btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color:#3c3f41;")
        sep2.setFixedWidth(1)
        lay.addWidget(sep2)

        # Color swatch button
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(52, 26)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setToolTip("Text colour (inline style)")
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_color_btn()
        lay.addWidget(self._color_btn)

        lay.addStretch()

        hint = QLabel("Select text then click a style")
        hint.setStyleSheet("color:#4b5563; font-size:11px;")
        lay.addWidget(hint)

        return self._format_bar

    # ── Shared button style helper ─────────────────────────────────────────────

    @staticmethod
    def _action_btn(label: str, bg: str, fg: str, border: str = "transparent") -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{bg}; color:{fg};
                border:1px solid {border}; border-radius:4px;
                padding:4px 14px; font-size:12px;
            }}
            QPushButton:hover {{ filter:brightness(1.15); }}
        """)
        return btn

    # ── Public API ────────────────────────────────────────────────────────────

    def show_file(self, path: Path) -> None:
        self._current_path = path
        self._title.setText(path.name)
        self._merge_btn.setVisible(self._guide_path is not None)
        self._send_btn_bar.setVisible(True)
        if self._code_mode:
            self._code_editor.setPlainText(path.read_text(encoding="utf-8"))
        else:
            self._view.load(QUrl.fromLocalFile(str(path)))

    def clear(self) -> None:
        self._current_path = None
        self._view.setHtml("")
        self._title.setText("Select a template")
        self._send_btn_bar.setVisible(False)

    def set_guide_path(self, path: Path | None) -> None:
        self._guide_path = path
        self._merge_btn.setVisible(path is not None and self._current_path is not None)

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    def is_dirty(self) -> bool:
        if self._code_mode:
            return self._code_editor.document().isModified()
        return self._dirty

    def save(self, on_done: callable = None) -> None:
        """Save current file. Calls on_done() when complete (async-safe)."""
        if not self._current_path:
            if on_done:
                on_done()
            return
        if self._code_mode:
            self._write_to_file(self._code_editor.toPlainText())
            if on_done:
                on_done()
        else:
            def _cb(html: str) -> None:
                self._write_to_file(html)
                if on_done:
                    on_done()
            self._view.page().runJavaScript(_CLEANUP_JS, _cb)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_page_title_changed(self, title: str) -> None:
        if title == '__dirty__':
            self._dirty = True

    def _on_merge_clicked(self) -> None:
        if self._current_path and self._guide_path:
            self.merge_requested.emit(self._current_path, self._guide_path)

    def _on_load_finished(self, ok: bool) -> None:
        self._dirty = False
        if ok and self._edit_mode:
            self._view.page().runJavaScript(_EDIT_JS)

    def _toggle_code_mode(self, enabled: bool) -> None:
        self._code_mode = enabled
        self._view.setVisible(not enabled)
        self._code_editor.setVisible(enabled)
        self._save_btn.setVisible(enabled or self._edit_mode)
        self._format_bar.setVisible(self._edit_mode and not enabled)

        # Code mode and Edit mode are mutually exclusive
        self._edit_btn.setEnabled(not enabled)
        if enabled and self._edit_mode:
            self._edit_btn.setChecked(False)

        if enabled and self._current_path:
            html = self._current_path.read_text(encoding="utf-8")
            self._code_editor.setPlainText(html)
            self.status_message.emit("Code mode — editing raw HTML source")
        elif not enabled and self._current_path:
            # Apply code editor content back to the web view
            html = self._code_editor.toPlainText()
            self._view.setHtml(html, QUrl.fromLocalFile(str(self._current_path.parent) + "/"))
            self.status_message.emit(str(self._current_path))

    def _toggle_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self._save_btn.setVisible(enabled or self._code_mode)
        self._format_bar.setVisible(enabled and not self._code_mode)
        if not self._current_path:
            return
        if enabled:
            self._view.page().runJavaScript(_EDIT_JS)
            self.status_message.emit(
                "Edit mode ON — select text for formatting, click elements to delete"
            )
        else:
            self._view.load(QUrl.fromLocalFile(str(self._current_path)))
            self.status_message.emit(str(self._current_path))

    # ── Formatting ────────────────────────────────────────────────────────────

    def _fmt(self, cmd: str) -> None:
        self._view.page().runJavaScript(f"window.__fmt('{cmd}')")

    def _apply_size(self, px: int) -> None:
        self._view.page().runJavaScript(f"window.__applySize({px})")

    def _pick_color(self) -> None:
        # Save current selection before Qt opens the color dialog
        self._view.page().runJavaScript("window.__restoreSel && window.__restoreSel()")
        color = QColorDialog.getColor(self._last_color, self, "Pick text colour")
        if color.isValid():
            self._last_color = color
            self._refresh_color_btn()
            self._view.page().runJavaScript(f"window.__applyColor('{color.name()}')")

    def _refresh_color_btn(self) -> None:
        c = self._last_color.name()
        fg = "#ffffff" if self._last_color.lightness() < 128 else "#000000"
        self._color_btn.setStyleSheet(f"""
            QPushButton {{
                background:{c}; color:{fg}; border:1px solid #555;
                border-radius:4px; font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ border-color:#aaa; }}
        """)
        self._color_btn.setText(c.upper())

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        if not self._current_path:
            return
        if self._code_mode:
            self._write_to_file(self._code_editor.toPlainText())
        else:
            self._view.page().runJavaScript(_CLEANUP_JS, self._write_to_file)

    def _write_to_file(self, html: str) -> None:
        if not html or not self._current_path:
            return
        try:
            self._current_path.write_text(html, encoding="utf-8")
            self._dirty = False
            self._code_editor.document().setModified(False)
            self._save_btn.setText("Saved ✓")
            self._save_btn.setStyleSheet("""
                QPushButton { background:#065f46; color:#6ee7b7; border:none;
                    border-radius:4px; padding:4px 14px; font-size:12px; }
            """)
            self.status_message.emit(f"Saved: {self._current_path}")
            self._view.page().runJavaScript(_EDIT_JS)
            QTimer.singleShot(2000, self._reset_save_btn)
        except Exception as exc:
            self.status_message.emit(f"Save error: {exc}")

    def _reset_save_btn(self) -> None:
        self._save_btn.setText("Save")
        self._save_btn.setStyleSheet("""
            QPushButton { background:#059669; color:white; border:none;
                border-radius:4px; padding:4px 14px; font-size:12px; }
            QPushButton:hover { background:#047857; }
        """)
