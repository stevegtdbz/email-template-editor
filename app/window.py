from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from app import styles
from app.widgets.topbar import TopBar
from app.widgets.sidebar import Sidebar
from app.widgets.preview import PreviewPane
from app.widgets.merge_dialog import MergeDialog
from app.widgets.send_dialog import SendDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Email Template Batch Update Tool")
        self.setMinimumSize(1100, 700)
        self._guide_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._topbar = TopBar()
        self._topbar.open_folder_requested.connect(self._browse_folder)
        self._topbar.load_guide_requested.connect(self._load_guide)
        root.addWidget(self._topbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{styles.HANDLE};}}")

        self._sidebar = Sidebar()
        self._sidebar.file_selected.connect(self._on_file_selected)
        splitter.addWidget(self._sidebar)

        self._preview = PreviewPane()
        self._preview.status_message.connect(self.statusBar().showMessage)
        self._preview.merge_requested.connect(self._open_merge_dialog)
        self._preview.send_requested.connect(self._open_send_dialog)
        splitter.addWidget(self._preview)

        splitter.setSizes([240, 860])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        self.statusBar().setStyleSheet(
            f"background:{styles.BG_MID}; color:{styles.TEXT_MUTED}; font-size:12px;"
        )
        self.statusBar().showMessage("Ready")

    # ── Folder ────────────────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select folder with HTML templates")
        if path:
            self._load_directory(Path(path))

    def _load_directory(self, folder: Path) -> None:
        self._topbar.set_path(str(folder))
        self._preview.clear()
        n = self._sidebar.load_folder(folder)
        self.statusBar().showMessage(
            f"{n} template{'s' if n != 1 else ''} loaded from {folder}"
        )

    # ── Guide ─────────────────────────────────────────────────────────────────

    def _load_guide(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select guide template", "", "HTML files (*.html)"
        )
        if path:
            self._guide_path = Path(path)
            self._topbar.set_guide(self._guide_path.name)
            self._preview.set_guide_path(self._guide_path)
            self.statusBar().showMessage(f"Guide loaded: {self._guide_path}")

    # ── Template selection ────────────────────────────────────────────────────

    def _on_file_selected(self, path: Path) -> None:
        if self._preview.is_dirty() and self._preview.current_path != path:
            result = self._unsaved_dialog(self._preview.current_path.name)
            if result == "cancel":
                return
            if result == "save":
                self._preview.save(on_done=lambda: self._do_switch(path))
                return
            # "discard" — fall through
        self._do_switch(path)

    def _do_switch(self, path: Path) -> None:
        self._preview.show_file(path)
        self.statusBar().showMessage(str(path))

    def _unsaved_dialog(self, filename: str) -> str:
        """Show unsaved-changes dialog. Returns 'save', 'discard', or 'cancel'."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText(f"<b>{filename}</b> has unsaved changes.")
        msg.setInformativeText("Save before switching templates?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStyleSheet("QLabel { color: #e5e7eb; } QMessageBox { background: #2b2d30; }")

        save_btn    = msg.addButton("Save & Switch",   QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg.addButton("Discard Changes", QMessageBox.ButtonRole.DestructiveRole)
        _cancel_btn = msg.addButton("Cancel",          QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(save_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is save_btn:
            return "save"
        if clicked is discard_btn:
            return "discard"
        return "cancel"

    # ── Merge ─────────────────────────────────────────────────────────────────

    def _open_merge_dialog(self, source_path: Path, guide_path: Path) -> None:
        dlg = MergeDialog(source_path, guide_path, parent=self)
        dlg.merged.connect(self._on_merged)
        dlg.exec()

    def _open_send_dialog(self, source_path: Path) -> None:
        SendDialog(source_path, parent=self).exec()

    def _on_merged(self, path: Path) -> None:
        self._preview.show_file(path)
        self.statusBar().showMessage(f"Merged and saved: {path}")
