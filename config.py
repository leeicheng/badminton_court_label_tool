# ────────── 32 點之間要連的線（點編號從 1 起算）──────────
# 形式：(p1, p2, "color_name")
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen, QColor, QBrush

EDGES = [
    # ──藍色外框 & 頂／底橫──
    (1, 2, "blue"), (2, 3, "blue"), (3, 4, "blue"), (4, 5, "blue"),
    (1, 6, "blue"), (6, 11, "blue"), (11, 18, "blue"), (18, 23, "blue"), (23, 28, "blue"),
    (5, 10, "blue"), (10, 15, "blue"), (15, 22, "blue"), (22, 27, "blue"), (27, 32, "blue"),
    (28, 29, "blue"), (29, 30, "blue"), (30, 31, "blue"), (31, 32, "blue"),

    # ──黑色內框──
    (7, 6, "black"), (7, 2, "black"), (7, 8, "black"), (7, 12, "black"),
    (9, 8, "black"), (9, 4, "black"), (9, 10, "black"), (9, 14, "black"),
    (11, 16, "black"),
    (12, 11, "black"), (12, 13, "black"), (12, 19, "black"),
    (14, 13, "black"), (14, 15, "black"), (14, 21, "black"),
    (15, 17, "black"),
    (18, 16, "black"),
    (19, 18, "black"),(19, 24, "black"),(19, 20, "black"),
    (21, 20, "black"),(21, 22, "black"),(21, 26, "black"),
    (22, 17, "black"),
    (24, 23, "black"),(24, 25, "black"),(24, 29, "black"),
    (26, 25, "black"),(26, 27, "black"),(26, 31, "black"),

    # ──橘色中線──
    (3, 8,  "orange"), (8, 13, "orange"),
    (20, 25, "orange"), (25, 30, "orange"),

    # ──紅色發球線──
    (16, 17, "red"),
]

# 筆刷顏色對應
PENS = {
    "blue":   QPen(Qt.GlobalColor.cyan, 0),
    "black":  QPen(Qt.GlobalColor.black, 0),
    "orange": QPen(QColor("#f28d00"), 0),  # 自訂橘色
    "red":    QPen(Qt.GlobalColor.red, 0),
}

# ---------- 常數 ----------
MARK_RADIUS = 1
MAX_POINTS  = 32
POINT_FILE_SUFFIX = ".points.json"
IMG_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif", "*.tif")
PEN = QPen(Qt.GlobalColor.red, 0)
BRUSH = QBrush(Qt.GlobalColor.red)