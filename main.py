#!/usr/bin/env python3
"""mark32.py – PyQt6 羽球場 32 點標記工具（表格版 + 自動連線）

功能一覽
========
* 左鍵標點：即時把 X/Y 寫入表格並自動跳到下一列。
* 右鍵清空：座標設為 Null，畫布移除標記，Is Null 會被打勾。
* Visible = Checked → 畫圓點；Unchecked → 畫 X。
* 勾選 Is Null → 取消顯示。
* 依照 EDGES 對照表自動連線，並用 color_name 指定顏色。

依序改動
--------
1. 新增 `EDGES` & `PENS` 常數來定義要連的線段與顏色。
2. `ImageCanvas` 新增 `edge_items` 字典 + `update_edges_for()` 來管理線段。
3. 在標點、清空、Visible/Null 變動時都呼叫 `update_edges_for()`。
4. `load_image()` 載入舊點後呼叫一次所有 `update_edges_for()`，確保重畫連線。
"""

from __future__ import annotations

import sys
from PyQt6.QtWidgets import (
    QApplication
)
from gui_tool import MainWindow

# ---------- main ----------
if __name__=="__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())