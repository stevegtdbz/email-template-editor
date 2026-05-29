from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal
from app import styles


class Sidebar(QWidget):
    file_selected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)
        self.setStyleSheet(f"background:{styles.BG_DARK};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  TEMPLATES")
        header.setFixedHeight(34)
        header.setStyleSheet(
            f"color:{styles.TEXT_DIM}; font-size:10px; font-weight:bold; "
            f"letter-spacing:1px; background:{styles.BG_DARK};"
        )
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background:{styles.BG_DARK}; border:none;
                color:{styles.TEXT_LIST}; font-size:13px;
            }}
            QListWidget::item {{
                padding:9px 14px;
                border-bottom:1px solid {styles.ITEM_DIV};
            }}
            QListWidget::item:selected {{
                background:{styles.ITEM_SEL}; color:#ffffff;
            }}
            QListWidget::item:hover:!selected {{
                background:{styles.ITEM_HOV};
            }}
        """)
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

    def load_folder(self, folder: Path) -> int:
        self._list.clear()
        files = sorted(folder.rglob("*.html"))
        for f in files:
            item = QListWidgetItem(str(f.relative_to(folder)))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self._list.addItem(item)
        return len(files)

    def clear(self) -> None:
        self._list.clear()

    def _on_item_changed(self, current: QListWidgetItem, _) -> None:
        if current:
            self.file_selected.emit(current.data(Qt.ItemDataRole.UserRole))
