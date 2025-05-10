# content_switcher.py
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
import sys

# content_switcher.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QButtonGroup, QStackedWidget
)
from PyQt6.QtCore import Qt

class ContentSwitcher(QWidget):
    currentIndexChanged = pyqtSignal(int)               # ← 新 signal

    """
    Carbon-style Content Switcher.
    用法：
        sw = ContentSwitcher()
        sw.add_page("Players",   players_widget)
        sw.add_page("Stats",     stats_widget,  checked=True)
        sw.add_page("Settings",  settings_widget)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        self._bar_layout = QHBoxLayout(spacing=0)
        self._stack = QStackedWidget()

        root = QVBoxLayout(self)
        root.addLayout(self._bar_layout)
        root.addWidget(self._stack)

        # 點哪顆就切哪頁
        self._btn_group.idToggled.connect(self._on_tab_toggled)
        # 簡單 CSS，自己換成 Carbon token 就好
        self.setStyleSheet("""
        QPushButton[segment="true"]{
            border:1px solid #8d8d8d; background:#f4f4f4; padding:4px 12px;
        }
        QPushButton[segment="true"]:first-child{border-top-left-radius:4px;border-bottom-left-radius:4px;}
        QPushButton[segment="true"]:last-child {border-top-right-radius:4px;border-bottom-right-radius:4px;}
        QPushButton[segment="true"]:checked{
            background:#0f62fe; color:white; border:1px solid #0f62fe;
        }
        QPushButton[segment="true"]:hover{
            background:#e5e5e5;
        }
        """)

    # ────────────────────────────────────────────────
    def add_page(self, label: str, widget: QWidget, *, checked=False):
        """動態塞一頁進來。"""
        idx = self._stack.addWidget(widget)

        btn = QPushButton(label, checkable=True)
        btn.setProperty("segment", True)
        self._btn_group.addButton(btn, id=idx)
        self._bar_layout.addWidget(btn)

        if checked or idx == 0:
            btn.setChecked(True)
            self._stack.setCurrentIndex(idx)

    def _on_tab_toggled(self, idx: int, checked: bool):
        if checked:  # 只有被選中的那顆才算
            self._stack.setCurrentIndex(idx)  # 原本就要切頁
            self.currentIndexChanged.emit(idx)  # ← 對外 broadcast

if __name__ == "__main__":
    app = QApplication(sys.argv)
    switcher = ContentSwitcher()
    switcher.add_page("Players", QLabel("🧍‍♂️ 選手名單", alignment=Qt.AlignmentFlag.AlignCenter))
    switcher.add_page("Stats", QLabel("📊 數據分析", alignment=Qt.AlignmentFlag.AlignCenter), checked=True)
    switcher.add_page("Settings", QLabel("⚙️ 設定", alignment=Qt.AlignmentFlag.AlignCenter))
    switcher.resize(400, 200)
    switcher.show()
    sys.exit(app.exec())
