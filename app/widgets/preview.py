from pathlib import Path
import json as _json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QScrollArea,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from app import styles
from app.widgets.code_editor import CodeEditor


def _merge_css(base: str, override: str) -> str:
    """Merge two inline-style strings; override properties win."""
    def parse(css):
        d = {}
        for rule in css.split(';'):
            rule = rule.strip()
            if ':' in rule:
                p, _, v = rule.partition(':')
                k = p.strip().lower()
                if k:
                    d[k] = v.strip()
        return d
    merged = {**parse(base), **parse(override)}
    return ('; '.join(f'{k}: {v}' for k, v in merged.items()) + ';') if merged else ''


# ── Edit mode JS ──────────────────────────────────────────────────────────────
_EDIT_JS = """
(function () {
    if (window.__editModeActive) return;
    window.__editModeActive = true;

    var style = document.createElement('style');
    style.id = '__em_style__';
    style.textContent =
        '.__em_hov{outline:2px solid rgba(79,70,229,.7)!important;outline-offset:2px!important;}' +
        '.__em_sel{outline:2px solid rgba(220,38,38,.9)!important;outline-offset:2px!important;}';
    document.head.appendChild(style);

    document.body.contentEditable = 'true';
    var selected = null;
    var lastHov  = null;
    var __seq    = 0;
    window.__em_state = null;

    function setSelected(el) {
        if (selected) selected.classList.remove('__em_sel');
        selected = el;
        if (selected) {
            selected.classList.add('__em_sel');
            window.__em_state = {
                tag:   selected.tagName.toLowerCase(),
                style: selected.getAttribute('style') || '',
                seq:   ++__seq
            };
        } else {
            window.__em_state = null;
        }
    }

    document.addEventListener('mouseover', function (e) {
        if (lastHov && lastHov !== selected) lastHov.classList.remove('__em_hov');
        lastHov = e.target;
        if (lastHov !== selected) lastHov.classList.add('__em_hov');
    });
    document.addEventListener('mouseout', function (e) {
        if (e.target !== selected) e.target.classList.remove('__em_hov');
    });
    document.addEventListener('mousedown', function (e) {
        var tag = e.target.tagName;
        if (tag === 'BODY' || tag === 'HTML') return;
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault(); e.stopPropagation();
            if (selected === e.target) setSelected(null);
            e.target.remove();
        } else {
            setSelected(e.target);
        }
    }, true);

    window.__updateSelectedStyle = function (css) {
        if (!selected) return;
        if (css.trim()) selected.setAttribute('style', css);
        else            selected.removeAttribute('style');
    };
    window.__deleteSelected  = function () {
        if (selected) { selected.remove(); setSelected(null); }
    };
    window.__deselectElement = function () { setSelected(null); };

    setTimeout(function () {
        var obs = new MutationObserver(function () { document.title = '__dirty__'; });
        obs.observe(document.body, {
            childList: true, subtree: true,
            characterData: true, attributes: true,
        });
    }, 200);
})();
"""

_CLEANUP_JS = """
(function () {
    var s = document.getElementById('__em_style__'); if (s) s.remove();
    document.body.removeAttribute('contenteditable');
    document.querySelectorAll('.__em_hov,.__em_sel').forEach(function (el) {
        el.classList.remove('__em_hov', '__em_sel');
    });
    delete window.__editModeActive;
    delete window.__em_state;
    delete window.__updateSelectedStyle;
    delete window.__deleteSelected;
    delete window.__deselectElement;
    return document.documentElement.outerHTML;
})();
"""

_ICON_BTN = """
    QPushButton {{
        background:#2d2f34; color:{fg}; border:1px solid #3c3f41;
        border-radius:4px; font-size:12px;
    }}
    QPushButton:hover   {{ background:#3f4147; border-color:{hov}; color:{hfg}; }}
    QPushButton:pressed {{ background:{hov}; color:white; }}
"""


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
        self._last_em_seq = -1

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left pane ─────────────────────────────────────────────────────────
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        lv.addWidget(self._build_header_bar())

        self._view = QWebEngineView()
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.page().titleChanged.connect(self._on_page_title_changed)
        lv.addWidget(self._view)

        self._code_editor = CodeEditor()
        self._code_editor.setVisible(False)
        lv.addWidget(self._code_editor)

        root.addWidget(left, 1)

        # ── Right pane: style editor + style sets manager ─────────────────────
        root.addWidget(self._build_element_editor())

        # JS selection polling (50 ms)
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_selection)

        # Debounce for live style pushes
        self._style_push_timer = QTimer()
        self._style_push_timer.setSingleShot(True)
        self._style_push_timer.setInterval(120)
        self._style_push_timer.timeout.connect(self._push_style_to_element)

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

    def _build_element_editor(self) -> QWidget:
        self._element_editor = QWidget()
        self._element_editor.setFixedWidth(280)
        self._element_editor.setVisible(False)
        self._element_editor.setStyleSheet(
            f"background:{styles.BG_DARK}; border-left:1px solid #3c3f41;"
        )

        outer = QVBoxLayout(self._element_editor)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(38)
        hdr.setStyleSheet("background:#25272b; border-bottom:1px solid #3c3f41;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)

        self._elem_tag_label = QLabel("Style Editor")
        self._elem_tag_label.setStyleSheet(
            "color:#a5b4fc; font-size:13px; font-family:monospace; font-weight:bold;"
            "background:#25272b;"
        )
        hl.addWidget(self._elem_tag_label)
        hl.addStretch()

        desel_btn = QPushButton("✕")
        desel_btn.setFixedSize(24, 24)
        desel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        desel_btn.setToolTip("Deselect element")
        desel_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6b7280;border:none;font-size:14px;}"
            "QPushButton:hover{color:#e5e7eb;background:transparent;}"
        )
        desel_btn.clicked.connect(self._deselect_element)
        hl.addWidget(desel_btn)
        outer.addWidget(hdr)

        # ── Scrollable body ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:vertical{{background:{styles.BG_DARK};width:6px;border:none;}}"
            "QScrollBar::handle:vertical{background:#3c3f41;border-radius:3px;min-height:20px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        body = QWidget()
        body.setStyleSheet(f"background:{styles.BG_DARK};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(12, 12, 12, 12)
        bl.setSpacing(10)

        # ── Inline style section (shown only when element is selected) ─────────
        self._inline_style_section = QWidget()
        self._inline_style_section.setStyleSheet(f"background:{styles.BG_DARK};")
        self._inline_style_section.setVisible(False)
        ils = QVBoxLayout(self._inline_style_section)
        ils.setContentsMargins(0, 0, 0, 0)
        ils.setSpacing(6)
        ils.addWidget(self._section_label("INLINE STYLE"))

        self._inline_style_editor = QPlainTextEdit()
        self._inline_style_editor.setMinimumHeight(90)
        self._inline_style_editor.setMaximumHeight(200)
        self._inline_style_editor.setPlaceholderText("e.g. color: red; font-size: 16px;")
        self._inline_style_editor.setStyleSheet("""
            QPlainTextEdit {
                background:#1a1b1e; color:#e5e7eb;
                border:1px solid #3c3f41; border-radius:4px;
                font-family:monospace; font-size:12px; padding:6px;
                selection-background-color:#4f46e5;
            }
            QPlainTextEdit:focus { border-color:#4f46e5; }
        """)
        self._inline_style_editor.textChanged.connect(
            lambda: self._style_push_timer.start()
        )
        ils.addWidget(self._inline_style_editor)
        bl.addWidget(self._inline_style_section)

        # ── Style sets section (always visible in edit mode) ────────────────────
        sets_hdr = QWidget()
        sets_hdr.setStyleSheet(f"background:{styles.BG_DARK};")
        sh = QHBoxLayout(sets_hdr)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(4)
        sh.addWidget(self._section_label("STYLE SETS"))
        sh.addStretch()

        add_set_btn = QPushButton("+ New")
        add_set_btn.setFixedHeight(20)
        add_set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_set_btn.setStyleSheet("""
            QPushButton {
                background:#2d2f34; color:#a5b4fc; border:1px solid #3c3f41;
                border-radius:3px; padding:0 8px; font-size:11px;
            }
            QPushButton:hover   { background:#3f4147; border-color:#4f46e5; }
            QPushButton:pressed { background:#4f46e5; color:white; }
        """)
        add_set_btn.clicked.connect(self._add_style_set)
        sh.addWidget(add_set_btn)
        bl.addWidget(sets_hdr)

        self._elem_sets_container = QWidget()
        self._elem_sets_container.setStyleSheet(f"background:{styles.BG_DARK};")
        self._elem_sets_layout = QVBoxLayout(self._elem_sets_container)
        self._elem_sets_layout.setContentsMargins(0, 0, 0, 0)
        self._elem_sets_layout.setSpacing(4)
        bl.addWidget(self._elem_sets_container)

        bl.addStretch()

        # Delete element button (only when element is selected)
        self._delete_elem_btn = QPushButton("Delete Element")
        self._delete_elem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_elem_btn.setVisible(False)
        self._delete_elem_btn.setStyleSheet("""
            QPushButton {
                background:#7f1d1d; color:#fca5a5;
                border:1px solid #991b1b; border-radius:4px;
                padding:7px; font-size:13px;
            }
            QPushButton:hover   { background:#991b1b; color:white; }
            QPushButton:pressed { background:#b91c1c; }
        """)
        self._delete_elem_btn.clicked.connect(self._delete_selected_element)
        bl.addWidget(self._delete_elem_btn)

        scroll.setWidget(body)
        outer.addWidget(scroll)
        return self._element_editor

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color:#4b5563; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        return lbl

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
        self._last_em_seq = -1
        self._inline_style_section.setVisible(False)
        self._delete_elem_btn.setVisible(False)
        self._elem_tag_label.setText("Style Editor")
        if self._code_mode:
            self._code_editor.setPlainText(path.read_text(encoding="utf-8"))
        else:
            self._view.load(QUrl.fromLocalFile(str(path)))

    def clear(self) -> None:
        self._current_path = None
        self._view.setHtml("")
        self._title.setText("Select a template")
        self._send_btn_bar.setVisible(False)
        self._element_editor.setVisible(False)
        self._inline_style_section.setVisible(False)
        self._delete_elem_btn.setVisible(False)

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

    # ── Page events ───────────────────────────────────────────────────────────

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

    # ── Mode toggles ──────────────────────────────────────────────────────────

    def _toggle_code_mode(self, enabled: bool) -> None:
        self._code_mode = enabled
        self._view.setVisible(not enabled)
        self._code_editor.setVisible(enabled)
        self._save_btn.setVisible(enabled or self._edit_mode)

        self._edit_btn.setEnabled(not enabled)
        if enabled and self._edit_mode:
            self._edit_btn.setChecked(False)

        if enabled and self._current_path:
            self._code_editor.setPlainText(
                self._current_path.read_text(encoding="utf-8")
            )
            self.status_message.emit("Code mode — editing raw HTML source")
        elif not enabled and self._current_path:
            html = self._code_editor.toPlainText()
            self._view.setHtml(
                html, QUrl.fromLocalFile(str(self._current_path.parent) + "/")
            )
            self.status_message.emit(str(self._current_path))

    def _toggle_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self._save_btn.setVisible(enabled or self._code_mode)
        if enabled:
            self._elem_tag_label.setText("Style Editor")
            self._inline_style_section.setVisible(False)
            self._delete_elem_btn.setVisible(False)
            self._element_editor.setVisible(True)
            self._refresh_element_style_sets()
            self._poll_timer.start()
        else:
            self._poll_timer.stop()
            self._element_editor.setVisible(False)
            self._inline_style_section.setVisible(False)
            self._delete_elem_btn.setVisible(False)
            self._last_em_seq = -1
        if not self._current_path:
            return
        if enabled:
            self._view.page().runJavaScript(_EDIT_JS)
            self.status_message.emit(
                "Edit mode ON — click any element to edit its inline style"
            )
        else:
            self._view.load(QUrl.fromLocalFile(str(self._current_path)))
            self.status_message.emit(str(self._current_path))

    # ── JS selection polling ──────────────────────────────────────────────────

    def _poll_selection(self) -> None:
        self._view.page().runJavaScript(
            "JSON.stringify(window.__em_state || null)",
            self._handle_em_state,
        )

    def _handle_em_state(self, json_str: str) -> None:
        if not json_str or json_str == 'null':
            if self._inline_style_section.isVisible():
                self._inline_style_section.setVisible(False)
                self._delete_elem_btn.setVisible(False)
                self._elem_tag_label.setText("Style Editor")
            self._last_em_seq = -1
            return
        try:
            state = _json.loads(json_str)
        except Exception:
            return
        seq = state.get('seq', 0)
        if seq == self._last_em_seq:
            return
        self._last_em_seq = seq
        self._show_element_style(state.get('tag', '?'), state.get('style', ''))

    def _show_element_style(self, tag: str, style: str) -> None:
        self._elem_tag_label.setText(f"<{tag}>")
        self._inline_style_editor.blockSignals(True)
        self._inline_style_editor.setPlainText(style)
        self._inline_style_editor.blockSignals(False)
        self._refresh_element_style_sets()
        self._inline_style_section.setVisible(True)
        self._delete_elem_btn.setVisible(True)

    def _deselect_element(self) -> None:
        self._inline_style_section.setVisible(False)
        self._delete_elem_btn.setVisible(False)
        self._elem_tag_label.setText("Style Editor")
        self._last_em_seq = -1
        self._view.page().runJavaScript(
            "window.__deselectElement && window.__deselectElement()"
        )

    # ── Live style push ───────────────────────────────────────────────────────

    def _push_style_to_element(self) -> None:
        css = self._inline_style_editor.toPlainText()
        css_e = css.replace("\\", "\\\\").replace("'", "\\'")
        self._view.page().runJavaScript(
            f"window.__updateSelectedStyle && window.__updateSelectedStyle('{css_e}')"
        )

    # ── Style sets ────────────────────────────────────────────────────────────

    def _refresh_element_style_sets(self) -> None:
        from app import style_store
        while self._elem_sets_layout.count():
            item = self._elem_sets_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sets = style_store.load()
        if not sets:
            lbl = QLabel("No style sets yet — click + New to add one")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#4b5563; font-size:11px; font-style:italic;")
            self._elem_sets_layout.addWidget(lbl)
            return

        for i, s in enumerate(sets):
            row = QWidget()
            row.setStyleSheet(f"background:{styles.BG_DARK};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(3)

            apply_btn = QPushButton(s["name"])
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.setToolTip(s["value"])
            apply_btn.setStyleSheet("""
                QPushButton {
                    background:#2d2f34; color:#a5b4fc;
                    border:1px solid #3c3f41; border-radius:4px;
                    padding:5px 8px; font-size:12px; text-align:left;
                }
                QPushButton:hover   { background:#3f4147; border-color:#4f46e5; }
                QPushButton:pressed { background:#4f46e5; color:white; }
            """)
            apply_btn.clicked.connect(
                lambda _, css=s["value"]: self._apply_style_set_to_element(css)
            )
            rl.addWidget(apply_btn, 1)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(26, 26)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setToolTip("Edit style set")
            edit_btn.setStyleSheet(
                _ICON_BTN.format(fg="#9ca3af", hov="#4f46e5", hfg="#e5e7eb")
            )
            edit_btn.clicked.connect(lambda _, idx=i: self._edit_style_set_at(idx))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(26, 26)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("Delete style set")
            del_btn.setStyleSheet(
                _ICON_BTN.format(fg="#f87171", hov="#991b1b", hfg="#fca5a5")
            )
            del_btn.clicked.connect(lambda _, idx=i: self._delete_style_set_at(idx))
            rl.addWidget(del_btn)

            self._elem_sets_layout.addWidget(row)

    def _apply_style_set_to_element(self, css: str) -> None:
        current = self._inline_style_editor.toPlainText().strip()
        merged = _merge_css(current, css)
        self._inline_style_editor.blockSignals(True)
        self._inline_style_editor.setPlainText(merged)
        self._inline_style_editor.blockSignals(False)
        css_e = merged.replace("\\", "\\\\").replace("'", "\\'")
        self._view.page().runJavaScript(
            f"window.__updateSelectedStyle && window.__updateSelectedStyle('{css_e}')"
        )

    def _delete_selected_element(self) -> None:
        self._inline_style_section.setVisible(False)
        self._delete_elem_btn.setVisible(False)
        self._elem_tag_label.setText("Style Editor")
        self._last_em_seq = -1
        self._view.page().runJavaScript(
            "window.__deleteSelected && window.__deleteSelected()"
        )

    def _add_style_set(self) -> None:
        from app import style_store
        from app.widgets.style_sets_dialog import StyleSetDialog
        dlg = StyleSetDialog(parent=self)
        if dlg.exec() and dlg.style_name:
            sets = style_store.load()
            sets.append({"name": dlg.style_name, "value": dlg.style_value})
            style_store.save(sets)
            self._refresh_element_style_sets()

    def _edit_style_set_at(self, idx: int) -> None:
        from app import style_store
        from app.widgets.style_sets_dialog import StyleSetDialog
        sets = style_store.load()
        if idx >= len(sets):
            return
        s = sets[idx]
        dlg = StyleSetDialog(name=s["name"], value=s["value"], parent=self)
        if dlg.exec() and dlg.style_name:
            sets[idx] = {"name": dlg.style_name, "value": dlg.style_value}
            style_store.save(sets)
            self._refresh_element_style_sets()

    def _delete_style_set_at(self, idx: int) -> None:
        from app import style_store
        sets = style_store.load()
        if idx >= len(sets):
            return
        sets.pop(idx)
        style_store.save(sets)
        self._refresh_element_style_sets()

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
