from __future__ import annotations
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
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QCursor, QShortcut, QKeySequence
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
        self.template_labels: dict | None = None
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
        self.map = QLabel(self)

        # 原圖載入
        pixmap = QPixmap("./map.png")
        w, h = pixmap.width(), pixmap.height()
        scaled_pixmap = pixmap.scaled(w // 2, h // 2)

        # 縮圖處理
        self.map.setPixmap(scaled_pixmap)
        key_layout.addWidget(self.map)
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

        btn_template = QPushButton("套用到後續")  # ★ 新增
        btn_template.clicked.connect(self._set_template_from_current)

        # ------------ 整體右側佈局 ------------
        right_wrap = QWidget()
        right_layout = QVBoxLayout(right_wrap)
        right_layout.addLayout(h_btns)
        right_layout.addWidget(self.label_imgs)
        right_layout.addWidget(self.list_img)
        right_layout.addWidget(btn_template)
        right_layout.addWidget(switcher, 1)           # stretch=1 → 吃滿剩餘空間

        # ------------ 主視窗根佈局 ------------
        root = QHBoxLayout()
        root.addWidget(self.canvas, 1)
        root.addWidget(right_wrap)

        cw = QWidget(); cw.setLayout(root)
        self.setCentralWidget(cw)

        QShortcut(QKeySequence(Qt.Key.Key_Up), self).activated.connect(self.prev_img)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self).activated.connect(self.next_img)


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
        # ---------- 0. 如果有範本且檔案不存在，先準備相對→絕對 ----------
        fp = self._pts_path(idx)
        if not fp.exists() and self.template_labels:
            pix = QPixmap(self.img_paths[idx])
            iw, ih = pix.width(), pix.height()

            # 套用 points
            pts_raw = []
            for tp in self.template_labels["points"]:
                if tp is None:
                    pts_raw.append(None)
                else:
                    pts_raw.append(PointData(
                        x=tp["x"] * iw,
                        y=tp["y"] * ih,
                        visible=tp.get("visible", True)
                    ))

            # 套用 bboxes
            bbox_geos = []
            for tb in self.template_labels["bboxes"]:
                bbox_geos.append(QRectF(
                    tb["x"] * iw,
                    tb["y"] * ih,
                    tb["w"] * iw,
                    tb["h"] * ih
                ))
        else:
            # ---------- 1. 讀檔 (原本的整段搬進 else 分支) ----------
            pts_raw = [None] * MAX_POINTS
            bbox_geos = []
            if fp.exists():
                try:
                    raw = json.load(open(fp, "r", encoding="utf-8"))
                    if isinstance(raw, list):
                        raw = {"points": raw, "bboxes": []}

                    for ridx, data in enumerate(raw.get("points", [])):
                        if 0 <= ridx < MAX_POINTS:
                            pts_raw[ridx] = PointData(**data)

                    for b in raw.get("bboxes", []):
                        bbox_geos.append(QRectF(b["x"], b["y"], b["w"], b["h"]))
                except Exception as e:
                    print("讀取標註失敗：", e)

        # ---------- 2. 更新 state（以下跟你原本第 2、3、4 步一樣） ----------
        self.points = pts_raw
        self.bboxes.clear()
        self.update_bbox_table()
        for r in range(MAX_POINTS):
            self._sync_row(r, self.points[r])

        # 重新載圖（此步會清 scene & 重畫 keypoints）
        self.canvas.load_image(self.img_paths[idx])

        # 把 bbox 加回去
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

    def _set_template_from_current(self):
        """把目前圖片的標註存成範本，並立即套用到資料夾內所有缺少 .points.json 的圖片。"""
        if self.cur_idx < 0 or not self.img_paths:
            QMessageBox.warning(self, "還沒有圖片", "請先載入並標註第一張圖片")
            return

        # ── 1. 建立「相對座標」範本 ──────────────────────────
        pix = QPixmap(self.img_paths[self.cur_idx])
        iw, ih = pix.width(), pix.height()
        if iw == 0 or ih == 0:
            QMessageBox.warning(self, "無法讀取圖片", "圖片尺寸為 0?")
            return

        tmpl_pts = [
            None if p is None else {
                "x": p.x / iw,
                "y": p.y / ih,
                "visible": p.visible,
                "is_null": p.is_null  # 之後若要支援 is_null 再改
            }
            for p in self.points
        ]

        tmpl_boxes = []
        for r in self.bboxes:
            rect = r.rect()
            tmpl_boxes.append({
                "x": rect.x() / iw,
                "y": rect.y() / ih,
                "w": rect.width() / iw,
                "h": rect.height() / ih
            })

        self.template_labels = {"points": tmpl_pts, "bboxes": tmpl_boxes}

        # ── 2. 立即寫入所有缺檔的圖片 ────────────────────────
        created = 0
        for img_path in self.img_paths:
            pts_path = Path(img_path + POINT_FILE_SUFFIX)
            if pts_path.exists():  # 已經有標註檔就跳過
                continue

            # 依該張圖大小，把「相對範本」轉回「絕對 pixel 座標」
            pix = QPixmap(img_path)
            iw, ih = pix.width(), pix.height()
            if iw == 0 or ih == 0:
                continue

            pts_out = [
                None if p is None else {
                    "x": p["x"] * iw,
                    "y": p["y"] * ih,
                    "visible": p.get("visible", True),
                    "is_null": p.get("is_null", False)
                }
                for p in tmpl_pts
            ]
            boxes_out = [
                {
                    "x": b["x"] * iw,
                    "y": b["y"] * ih,
                    "w": b["w"] * iw,
                    "h": b["h"] * ih
                }
                for b in tmpl_boxes
            ]

            with open(pts_path, "w", encoding="utf-8") as f:
                json.dump({"points": pts_out, "bboxes": boxes_out},
                          f, indent=2, ensure_ascii=False)
            created += 1

        # ── 3. 完成訊息 ───────────────────────────────────
        QMessageBox.information(
            self,
            "範本已套用",
            f"完成！已為 {created} 張圖片建立 .points.json。"
            if created else "所有圖片都已經有 .points.json，不需再建立。"
        )

    # ----- close -----
    def closeEvent(self, e):
        self._save_points(self.cur_idx)
        super().closeEvent(e)