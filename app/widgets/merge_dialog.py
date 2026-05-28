from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QWidget,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from app import styles
from app.merger import merge_sections

# Injected into the source view.
# - Clicking any element walks up to the nearest <tr> (email-table semantics)
#   so clicking inside a row selects the whole row.
# - Selected rows get a green outline; toggling deselects.
# - document.title is updated to "__sel:N" so Python can track count via
#   the titleChanged signal without polling.
_SELECT_JS = """
(function () {
    if (window.__selMode) return;
    window.__selMode = true;

    var style = document.createElement('style');
    style.textContent =
        '.__h { outline:2px solid rgba(79,70,229,.7) !important;'
        + ' outline-offset:2px !important; cursor:pointer !important; }'
        + '.__s { outline:3px solid #10b981 !important;'
        + ' outline-offset:3px !important; background:rgba(16,185,129,.06) !important; }';
    document.head.appendChild(style);

    var selected = new Set();
    var lastHov  = null;

    function nearestTR(el) {
        var cur = el;
        while (cur && cur.tagName !== 'BODY' && cur.tagName !== 'HTML') {
            if (cur.tagName === 'TR') return cur;
            cur = cur.parentElement;
        }
        return el;
    }

    document.addEventListener('mouseover', function (e) {
        var t = nearestTR(e.target);
        if (t === document.body || t === document.documentElement) return;
        if (lastHov && lastHov !== t && !selected.has(lastHov)) lastHov.classList.remove('__h');
        lastHov = t;
        if (!selected.has(t)) t.classList.add('__h');
    });

    document.addEventListener('mouseout', function (e) {
        var t = nearestTR(e.target);
        if (t && !selected.has(t)) t.classList.remove('__h');
    });

    document.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var t = nearestTR(e.target);
        if (t === document.body || t === document.documentElement) return;
        if (selected.has(t)) {
            selected.delete(t);
            t.classList.remove('__s');
            t.classList.add('__h');
        } else {
            selected.add(t);
            t.classList.remove('__h');
            t.classList.add('__s');
        }
        document.title = '__sel:' + selected.size;
    }, true);

    window.__getSelected = function () {
        // Return outerHTML in DOM order
        var arr = Array.from(selected);
        arr.sort(function (a, b) {
            return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });
        return arr.map(function (el) {
            el.classList.remove('__s', '__h');
            var h = el.outerHTML;
            el.classList.add('__s');
            return h;
        });
    };
})();
"""


def _panel(label_text: str) -> tuple[QWidget, QWebEngineView]:
    """Return a labelled panel widget and its embedded QWebEngineView."""
    container = QWidget()
    container.setStyleSheet(f"background:{styles.BG_DARK};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    header = QLabel(f"  {label_text}")
    header.setFixedHeight(32)
    header.setStyleSheet(
        f"color:{styles.TEXT_DIM}; font-size:10px; font-weight:bold; "
        f"letter-spacing:1px; background:{styles.BG_MID};"
    )
    layout.addWidget(header)

    view = QWebEngineView()
    layout.addWidget(view)
    return container, view


class MergeDialog(QDialog):
    """Two-panel dialog: left = source template (click rows to select),
    right = live merge preview using the guide template."""

    merged = pyqtSignal(Path)

    def __init__(self, source_path: Path, guide_path: Path, parent=None):
        super().__init__(parent)
        self._source_path = source_path
        self._guide_path  = guide_path
        self._guide_html  = guide_path.read_text(encoding='utf-8')
        self._merged_html: str | None = None

        self.setWindowTitle(
            f"Merge  ·  {source_path.name}  →  {guide_path.name}"
        )
        self.resize(1400, 820)
        self._setup_ui()
        self._load_views()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Info bar
        info = QWidget()
        info.setFixedHeight(44)
        info.setStyleSheet(f"background:{styles.BG_MID};border-bottom:1px solid #3c3f41;")
        il = QHBoxLayout(info)
        il.setContentsMargins(16, 0, 16, 0)
        il.setSpacing(6)

        def _chip(text, color="#374151"):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"background:{color};color:#e5e7eb;font-size:12px;"
                f"border-radius:4px;padding:3px 10px;"
            )
            return lbl

        il.addWidget(_chip(f"Source: {self._source_path.name}"))
        arrow = QLabel("→")
        arrow.setStyleSheet(f"color:{styles.TEXT_MUTED};font-size:14px;")
        il.addWidget(arrow)
        il.addWidget(_chip(f"Guide: {self._guide_path.name}", "#1e3a5f"))
        il.addStretch()

        hint = QLabel("Click rows on the left to select · Preview updates on right")
        hint.setStyleSheet(f"color:{styles.TEXT_MUTED};font-size:11px;")
        il.addWidget(hint)
        root.addWidget(info)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{styles.HANDLE};}}")

        left_panel, self._source_view = _panel("SELECT SECTIONS TO KEEP  (click rows)")
        self._source_view.titleChanged.connect(self._on_title_changed)
        self._source_view.loadFinished.connect(self._on_source_loaded)
        splitter.addWidget(left_panel)

        right_panel, self._preview_view = _panel("MERGE PREVIEW")
        splitter.addWidget(right_panel)

        splitter.setSizes([700, 700])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Bottom bar
        bottom = QWidget()
        bottom.setFixedHeight(54)
        bottom.setStyleSheet(f"background:{styles.BG_MID};border-top:1px solid #3c3f41;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(10)

        self._status = QLabel("Click rows in the source template to select sections")
        self._status.setStyleSheet(f"color:{styles.TEXT_MUTED};font-size:12px;")
        bl.addWidget(self._status)
        bl.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet("""
            QPushButton { background:#374151; color:#e5e7eb; border:none;
                border-radius:5px; padding:7px 18px; font-size:13px; }
            QPushButton:hover { background:#4b5563; }
        """)
        cancel.clicked.connect(self.reject)
        bl.addWidget(cancel)

        self._merge_btn = QPushButton("Merge & Save")
        self._merge_btn.setEnabled(False)
        self._merge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._merge_btn.setStyleSheet("""
            QPushButton { background:#4f46e5; color:white; border:none;
                border-radius:5px; padding:7px 18px; font-size:13px; }
            QPushButton:hover    { background:#4338ca; }
            QPushButton:disabled { background:#374151; color:#6b7280; }
        """)
        self._merge_btn.clicked.connect(self._merge_and_save)
        bl.addWidget(self._merge_btn)

        root.addWidget(bottom)

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load_views(self) -> None:
        self._source_view.load(QUrl.fromLocalFile(str(self._source_path)))
        self._preview_view.load(QUrl.fromLocalFile(str(self._guide_path)))

    def _on_source_loaded(self, ok: bool) -> None:
        if ok:
            self._source_view.page().runJavaScript(_SELECT_JS)

    # ── Selection tracking ────────────────────────────────────────────────────

    def _on_title_changed(self, title: str) -> None:
        if not title.startswith('__sel:'):
            return
        n = int(title[6:])
        if n == 0:
            self._status.setText("Click rows in the source template to select sections")
            self._merge_btn.setEnabled(False)
        else:
            self._status.setText(f"{n} section{'s' if n != 1 else ''} selected — preview updating…")
            self._merge_btn.setEnabled(True)
            # Auto-refresh preview whenever selection changes
            self._source_view.page().runJavaScript(
                'window.__getSelected()', self._update_preview
            )

    # ── Preview ───────────────────────────────────────────────────────────────

    def _update_preview(self, parts: list) -> None:
        if not parts:
            return
        self._merged_html = merge_sections(self._guide_html, parts)
        n = len(parts)
        self._status.setText(f"{n} section{'s' if n != 1 else ''} selected — ready to merge")
        self._preview_view.setHtml(
            self._merged_html,
            QUrl.fromLocalFile(str(self._guide_path.parent) + '/'),
        )

    # ── Save ──────────────────────────────────────────────────────────────────

    def _merge_and_save(self) -> None:
        if not self._merged_html:
            return
        self._source_path.write_text(self._merged_html, encoding='utf-8')
        self.merged.emit(self._source_path)
        self.accept()
