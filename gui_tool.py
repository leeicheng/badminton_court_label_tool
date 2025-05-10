import json, sys, glob
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QLabel,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHBoxLayout, QVBoxLayout, QMessageBox,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsItemGroup, QPushButton, QListWidget, QGraphicsRectItem, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QCursor
from PyQt6.QtCore import Qt, QRectF, QPointF
from networkx.classes import add_path

from canvas import ImageCanvas
from config import MAX_POINTS, POINT_FILE_SUFFIX, IMG_EXTS
from point_data import PointData
from ui_content_switcher import ContentSwitcher


from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QListWidget, QTableWidget, QPushButton,
    QHBoxLayout, QVBoxLayout, QSizePolicy
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("32-Point Court Marker")
        self.resize(1280, 840)

        # ------------ 狀態資料 ------------
        self.mode = "point"
        self.bboxes: list[QGraphicsRectItem] = []
        self.points: List[Optional[PointData]] = [None] * MAX_POINTS
        self.active_idx: Optional[int] = None
        self.img_paths: List[str] = []
        self.cur_idx: int = -1

        # ------------ 左側畫布 ------------
        self.canvas = ImageCanvas(self)

        # ------------ 右側 ContentSwitcher ------------
        switcher = ContentSwitcher(self)
        switcher.setSizePolicy(QSizePolicy.Policy.Preferred,
                               QSizePolicy.Policy.Expanding)
        switcher.currentIndexChanged.connect(self._switch_mode_by_page)

        # ①── Keypoints 頁面 ---------------------------------
        key_widget = QWidget()
        bbox_widget = QWidget()
        key_layout = QVBoxLayout(key_widget)
        bbox_layout = QVBoxLayout(bbox_widget)

        self.label_imgs = QLabel("影像檔")
        self.table_pts  = self._create_table()
        self.list_img   = QListWidget()
        self.list_img.currentRowChanged.connect(self._on_image_change)

        btn_open = QPushButton("選擇資料夾"); btn_open.clicked.connect(self._select_dir)
        btn_prev = QPushButton("← 上一張");   btn_prev.clicked.connect(self.prev_img)
        btn_next = QPushButton("下一張 →");   btn_next.clicked.connect(self.next_img)

        # — 上方功能列 —
        h_btns = QHBoxLayout()
        h_btns.addWidget(btn_open)
        h_btns.addStretch()
        h_btns.addWidget(btn_prev)
        h_btns.addWidget(btn_next)


        # — 塞進 key_layout —
        key_layout.addWidget(self.table_pts)
        key_layout.addStretch()

        self.lbl_bbox_cnt = QLabel("已標記 BBox：0")
        self.tbl_bbox = QTableWidget(0, 5)  # cols: idx, x1, y1, x2, y2
        self.tbl_bbox.setHorizontalHeaderLabels(["#", "x1", "y1", "x2", "y2"])
        self.tbl_bbox.verticalHeader().setVisible(False)
        self.tbl_bbox.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_bbox.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        bbox_layout.addWidget(self.lbl_bbox_cnt)
        bbox_layout.addWidget(self.tbl_bbox, 1)  # stretch=1，表格撐滿

        switcher.add_page("Keypoints", key_widget)    # ▼ 修正：傳 widget，不是 layout
        switcher.add_page("bbox", bbox_widget)


        # ------------ 整體右側佈局 ------------
        right_wrap = QWidget()
        right_layout = QVBoxLayout(right_wrap)
        right_layout.addLayout(h_btns)
        right_layout.addWidget(self.label_imgs)
        right_layout.addWidget(self.list_img)
        right_layout.addWidget(switcher, 1)           # stretch=1 → 吃滿剩餘空間

        # ------------ 主視窗根佈局 ------------
        root = QHBoxLayout()
        root.addWidget(self.canvas, 1)
        root.addWidget(right_wrap)

        cw = QWidget(); cw.setLayout(root)
        self.setCentralWidget(cw)


    # ----- table -----
    def _create_table(self) -> QTableWidget:
        tbl = QTableWidget(MAX_POINTS, 5)
        tbl.setHorizontalHeaderLabels(["Keypoint id", "X", "Y", "Visible", "Is Null"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tbl.itemSelectionChanged.connect(self._row_selected)
        tbl.itemChanged.connect(self._cell_changed)

        tbl.blockSignals(True)  # 避免初始化觸發
        for r in range(MAX_POINTS):
            tbl.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            tbl.setItem(r, 1, QTableWidgetItem(""))
            tbl.setItem(r, 2, QTableWidgetItem(""))

            vis = QTableWidgetItem()
            vis.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            vis.setCheckState(Qt.CheckState.Unchecked)
            tbl.setItem(r, 3, vis)

            nul = QTableWidgetItem()
            nul.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            nul.setCheckState(Qt.CheckState.Unchecked)
            tbl.setItem(r, 4, nul)
        tbl.blockSignals(False)
        tbl.resizeColumnsToContents()
        return tbl

    def update_bbox_table(self):
        """重新整理 BBox 計數 & 座標表。"""
        cnt = len(self.bboxes)
        self.lbl_bbox_cnt.setText(f"已標記 BBox：{cnt}")

        self.tbl_bbox.setRowCount(cnt)
        for i, rect in enumerate(self.bboxes):
            x1, y1 = int(rect.rect().x()), int(rect.rect().y())
            x2 = int(rect.rect().x() + rect.rect().width())
            y2 = int(rect.rect().y() + rect.rect().height())

            self.tbl_bbox.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.tbl_bbox.setItem(i, 1, QTableWidgetItem(str(x1)))
            self.tbl_bbox.setItem(i, 2, QTableWidgetItem(str(y1)))
            self.tbl_bbox.setItem(i, 3, QTableWidgetItem(str(x2)))
            self.tbl_bbox.setItem(i, 4, QTableWidgetItem(str(y2)))

        self.tbl_bbox.resizeColumnsToContents()

    # ----- table events -----
    def _row_selected(self):
        sel = self.table_pts.selectedItems()
        self.active_idx = sel[0].row() if sel else None
        self.canvas.highlight(self.active_idx)

    def _cell_changed(self, item: QTableWidgetItem):
        row, col = item.row(), item.column()
        pd = self.points[row]
        if col == 3 and pd:           # Visible toggle
            pd.visible = item.checkState() == Qt.CheckState.Checked
            self.canvas._draw(row, pd)
            self.canvas.update_edges_for(row)
        elif col == 4:                # Is Null toggle
            if item.checkState() == Qt.CheckState.Checked:
                self.clear_point(row)
                self.canvas._remove(row)
                self.canvas.update_edges_for(row)

    def _switch_mode_by_page(self, idx: int):
        # 0 = Keypoints, 1 = BBox（照你 add_page 的順序）
        self.mode = "point" if idx == 0 else "bbox"
        # 切 page 時把高亮清掉，避免 user 誤會
        self.canvas.highlight(None)
        self.active_idx = None

    def select_next_row(self):
        if self.active_idx is None:
            return
        nxt = self.active_idx + 1
        if nxt < MAX_POINTS:
            self.table_pts.setCurrentCell(nxt, 0)

    def select_row(self, idx: int):
        self.table_pts.selectRow(idx)
        self.active_idx = idx

    # ----- point helpers -----
    def set_point(self, idx: int, pd: PointData):
        self.points[idx] = pd
        self._sync_row(idx, pd)
        self.canvas.update_edges_for(idx)

    def clear_point(self, idx: int):
        self.points[idx] = None
        self._sync_row(idx, None)
        self.canvas.update_edges_for(idx)

    def _sync_row(self, idx: int, pd: Optional[PointData]):
        self.table_pts.blockSignals(True)
        if pd is None:
            for c in (1, 2):
                self.table_pts.item(idx, c).setText("")
            self.table_pts.item(idx, 3).setCheckState(Qt.CheckState.Unchecked)
            self.table_pts.item(idx, 4).setCheckState(Qt.CheckState.Checked)
        else:
            self.table_pts.item(idx, 1).setText(str(int(pd.x)))
            self.table_pts.item(idx, 2).setText(str(int(pd.y)))
            self.table_pts.item(idx, 3).setCheckState(
                Qt.CheckState.Checked if pd.visible else Qt.CheckState.Unchecked
            )
            self.table_pts.item(idx, 4).setCheckState(Qt.CheckState.Unchecked)
        self.table_pts.blockSignals(False)

    # ----- image list -----
    def _select_dir(self):
        d = QFileDialog.getExistingDirectory(self, "選擇圖片資料夾")
        if not d:
            return
        self.img_paths = sorted({
            p for ext in IMG_EXTS for p in glob.glob(str(Path(d) / "**" / ext), recursive=True)
        })
        if not self.img_paths:
            QMessageBox.information(self, "沒有圖片", "資料夾裡沒有支援格式的圖片")
            return
        self.list_img.clear()
        self.list_img.addItems([Path(p).name for p in self.img_paths])
        self.list_img.setCurrentRow(0)

    def _on_image_change(self, row: int):
        if row < 0 or row >= len(self.img_paths):
            return
        if self.cur_idx >= 0:
            self._save_points(self.cur_idx)
        self.cur_idx = row
        self._update_title()
        self._load_points(row)

    def prev_img(self):
        self.list_img.setCurrentRow(max(0, self.list_img.currentRow() - 1))

    def next_img(self):
        self.list_img.setCurrentRow(
            min(len(self.img_paths) - 1, self.list_img.currentRow() + 1)
        )

    def _update_title(self):
        txt = "影像檔" if not self.img_paths else f"影像檔 ({self.cur_idx + 1}/{len(self.img_paths)})"
        self.label_imgs.setText(txt)

    # ----- JSON -----
    def _pts_path(self, idx: int) -> Path:
        return Path(self.img_paths[idx] + POINT_FILE_SUFFIX)

    def _load_points(self, idx: int):
        # ---------- 1. 讀檔 ----------
        pts_raw   = [None] * MAX_POINTS
        bbox_geos = []                      # 暫存幾何資料，等畫面清完再 addRect()

        fp = self._pts_path(idx)
        if fp.exists():
            try:
                raw = json.load(open(fp, "r", encoding="utf-8"))
                # 舊格式只有 list → 包成 dict
                if isinstance(raw, list):
                    raw = {"points": raw, "bboxes": []}

                # points
                for ridx, data in enumerate(raw.get("points", [])):
                    if 0 <= ridx < MAX_POINTS and not data.get("is_null", False):
                        pts_raw[ridx] = PointData(**data)

                # bboxes：先存成 QRectF
                for b in raw.get("bboxes", []):
                    bbox_geos.append(QRectF(b["x"], b["y"], b["w"], b["h"]))

            except Exception as e:
                print("讀取標註失敗：", e)

        # ---------- 2. 更新 state ----------
        self.points = pts_raw
        self.bboxes.clear()
        self.update_bbox_table()
        for r in range(MAX_POINTS):
            self._sync_row(r, self.points[r])

        # ---------- 3. 重新載圖（這一步會清 scene & 重畫 keypoints） ----------
        self.canvas.load_image(self.img_paths[idx])

        # ---------- 4. 把 bbox 加回去 ----------
        for rectf in bbox_geos:
            item = self.canvas.scene().addRect(rectf, QPen(Qt.GlobalColor.green, 0))
            item.setZValue(1)
            self.bboxes.append(item)
        self.update_bbox_table()

    def _save_points(self, idx: int):
        if idx < 0:
            return
        pts_out = [
            asdict(p) if p and not p.is_null else
            {"x": 0, "y": 0, "visible": False, "is_null": True}
            for p in self.points
        ]
        bboxes_out = [
            {"x": r.rect().x(), "y": r.rect().y(),
             "w": r.rect().width(), "h": r.rect().height()}
            for r in self.bboxes
        ]
        with open(self._pts_path(idx), "w", encoding="utf-8") as f:
            json.dump({"points": pts_out, "bboxes": bboxes_out},
                      f, indent=2, ensure_ascii=False)

    # ----- close -----
    def closeEvent(self, e):
        self._save_points(self.cur_idx)
        super().closeEvent(e)