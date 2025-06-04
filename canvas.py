from __future__ import annotations

from typing import Optional, List
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsItemGroup, QGraphicsRectItem, QMessageBox,
    QMenu,
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QCursor, QAction
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.sip import isdeleted

from point_data import PointData
import config
import gui_tool
class ImageCanvas(QGraphicsView):
    """負責顯示影像、標點、畫邊和輔助線。"""

    # ── 建構子 ──────────────────────────────────────────────────────────
    def __init__(self, parent: "MainWindow"):
        super().__init__(parent)
        self._mw: gui_tool.MainWindow = parent

        # Scene & 基本設定
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        # 狀態
        self.point_items: list[Optional[QGraphicsItemGroup]] = [None] * config.MAX_POINTS
        self.edge_items: dict[tuple[int, int], QGraphicsLineItem] = {}
        self._zoom: int = 0
        self._panning: bool = False

        # 十字線
        self._create_guides()
        self._selected_idx: Optional[int] = None        # ← 現在選到哪個點
        self._highlight_pen = QPen(Qt.GlobalColor.yellow, 1)  # 黃框

        self._bbox_start: Optional[QPointF] = None
        self._bbox_temp: Optional[QGraphicsRectItem] = None

    # ── 給外部呼叫：切換 highlight ──────────────────────────────
    def highlight(self, idx: Optional[int]):
        """把指定 idx 畫黃框，其餘恢復原色；idx=None 代表全部取消。"""
        if idx is not None and (idx >= len(self.point_items) or not self.point_items[idx] or isdeleted(
            self.point_items[idx])): idx = None
        # 1) 先還原舊的
        if self._selected_idx is not None:
            self._set_group_pen(self._selected_idx, config.PEN)  # 原本紅色
        # 2) 再給新的
        self._selected_idx = idx
        if idx is not None:
            self._set_group_pen(idx, self._highlight_pen)

    # ── 私用：把 group 底下所有 child item 改成指定 pen ────────────
    def _set_group_pen(self, idx: int, pen: QPen):
        grp = self.point_items[idx]

        # A. group 本身就已經被 C++ delete？直接跳過
        if not grp or isdeleted(grp):
            return

        # B. 逐一檢查底下 child，活著的才 setPen
        for child in grp.childItems():
            if isdeleted(child):
                continue
            if isinstance(child, (QGraphicsEllipseItem, QGraphicsLineItem)):
                child.setPen(pen)
    # ── 私用：重建十字線 ────────────────────────────────────────────
    def _create_guides(self):
        guide_pen = QPen(Qt.GlobalColor.green, 0, Qt.PenStyle.DashLine)
        self.h_line: QGraphicsLineItem = self.scene().addLine(0, 0, 0, 0, guide_pen)
        self.v_line: QGraphicsLineItem = self.scene().addLine(0, 0, 0, 0, guide_pen)
        for ln in (self.h_line, self.v_line):
            ln.setZValue(2)
            ln.setVisible(False)

    # ── 滾輪縮放 ─────────────────────────────────────────────────────
    def wheelEvent(self, e):
        factor = 1.25 if e.angleDelta().y() > 0 else 1 / 1.25
        self._zoom += 1 if factor > 1 else -1
        if self._zoom < -10:
            self._zoom = -10
            return
        self.scale(factor, factor)

        # 若十字線可見，強制更新一次長度
        if self.h_line.isVisible():
            pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
            rect = self.sceneRect()
            self.h_line.setLine(rect.left(), pos.y(), rect.right(), pos.y())
            self.v_line.setLine(pos.x(), rect.top(), pos.x(), rect.bottom())

    # ── 滑鼠移動：更新十字線 ────────────────────────────────────────
    def mouseMoveEvent(self, e):
        if self._mw.mode == "bbox" and self._bbox_temp is not None:
            pos = self.mapToScene(e.position().toPoint())
            rect = QRectF(self._bbox_start, pos).normalized()
            self._bbox_temp.setRect(rect)
        pos = self.mapToScene(e.position().toPoint())
        if self.h_line.isVisible():
            rect = self.sceneRect()
            self.h_line.setLine(rect.left(), pos.y(), rect.right(), pos.y())
            self.v_line.setLine(pos.x(), rect.top(), pos.x(), rect.bottom())
        super().mouseMoveEvent(e)

    # ── 滑鼠進出：顯示 / 隱藏十字線 ────────────────────────────────
    def enterEvent(self, e):
        for ln in (self.h_line, self.v_line):
            ln.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        for ln in (self.h_line, self.v_line):
            ln.setVisible(False)
        super().leaveEvent(e)

    # ── 中鍵平移 & 左/右鍵標點 ───────────────────────────────────────
    def mousePressEvent(self, e):
        # ───────── BBox 模式 ─────────
        if self._mw.mode == "bbox":
            if e.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(e.position().toPoint())
                if self._bbox_start is None:
                    # 第一下：記住起點 & 建 temp rect
                    self._bbox_start = pos
                    self._bbox_temp = self.scene().addRect(
                        QRectF(pos, pos), QPen(Qt.GlobalColor.green, 0))
                    self._bbox_temp.setZValue(1)
                else:
                    # 第二下：固定 bbox
                    rect = QRectF(self._bbox_start, pos).normalized()
                    if rect.width() > 3 and rect.height() > 3:  # 過小就丟掉
                        self._bbox_temp.setRect(rect)
                        self._mw.bboxes.append(self._bbox_temp)
                        self._mw.update_bbox_table()
                    else:
                        self.scene().removeItem(self._bbox_temp)
                    self._bbox_start = None
                    self._bbox_temp = None
                return

            elif e.button() == Qt.MouseButton.RightButton:
                # 檢查有沒有點到 bbox → 刪除
                pos = self.mapToScene(e.position().toPoint())
                for rect in reversed(self._mw.bboxes):  # 從上層往下找
                    if rect.contains(pos):
                        self.scene().removeItem(rect)
                        self._mw.bboxes.remove(rect)
                        self._mw.update_bbox_table()
                        break
                return

        # ───────── 中鍵：彈選單 → 標點 ─────────
        if e.button() == Qt.MouseButton.MiddleButton:
            scene_pos = self.mapToScene(e.position().toPoint())
            idx = self._popup_id_menu(e.globalPosition().toPoint())
            if idx is not None:
                self._mark_point(idx, scene_pos)
            return  # 吃掉事件

        # ───────── 左鍵點擊：先確定是不是點到既有點 ─────────
        if e.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(e.position().toPoint())

            # 1) 命中測試：小方塊內找 group
            hit_rect = QRectF(scene_pos.x() - config.MARK_RADIUS,
                              scene_pos.y() - config.MARK_RADIUS,
                              config.MARK_RADIUS * 2, config.MARK_RADIUS * 2)
            for it in self.scene().items(hit_rect):
                grp = it
                while grp and not isinstance(grp, QGraphicsItemGroup):
                    grp = grp.parentItem()
                if grp and grp.data(0) is not None:
                    idx = int(grp.data(0))
                    self._mw.select_row(idx)
                    self.highlight(idx)
                    return

            # 2) 沒打到現有點 → 用 active_idx 畫新點
            idx = self._mw.active_idx
            if idx is None:
                QMessageBox.information(self, "先選 Keypoint", "請在右側表格選擇要標記的列。")
                return
            self._mark_point(idx, scene_pos)
            return

        # ───────── 右鍵：清除當前 active_idx ─────────
        if e.button() == Qt.MouseButton.RightButton:
            idx = self._mw.active_idx
            if idx is not None:
                pd = self._mw.points[idx]

                # 如果目前沒有資料，或之前就已經刪掉了，就不必做事
                if pd is None or pd.is_null:
                    return

                if pd.visible:
                    # 【第一下】把 visible 改成 False，畫成叉叉
                    pd.visible = False
                    self._mw.set_point(idx, pd)  # 更新資料模型
                    self._draw(idx, pd)  # 重新繪製這個點
                else:
                    # 【第二下】已經是 invisible，再右鍵就真正刪除
                    self._mw.clear_point(idx)  # 把資料設為 is_null
                    self._remove(idx)  # 從畫面移除
                # 無論第一下或第二下，都要刷新相關邊
                self.update_edges_for(idx)
            return

        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._panning and e.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self._panning = False
        super().mouseReleaseEvent(e)

    # ── 載入影像 ─────────────────────────────────────────────────────
    def load_image(self, path: str):
        # ---------- A. 先斷開所有 Python 端引用 ----------
        print(path)
        self.highlight(None)
        self.edge_items.clear()  # ① 把線的 dict 先清掉
        self.point_items = [None] * config.MAX_POINTS  # ② 點的 group 清單也丟掉

        # 清場但保留十字線：先把 guide 的指標留著，清完再重建
        self.scene().clear()
        self._create_guides()
        self._mw.bboxes.clear()
        # self.resetTransform()
        # self._zoom = 0

        pm = QPixmap(path)
        pix = self.scene().addPixmap(pm)
        pix.setZValue(-100)
        self.setSceneRect(QRectF(pm.rect()))

        # 重新畫現有點
        for i, pd in enumerate(self._mw.points):
            if pd and not pd.is_null:
                self._draw(i, pd)
        # 更新邊
        for i in range(config.MAX_POINTS):
            self.update_edges_for(i)

    # ── 畫 / 清點 ────────────────────────────────────────────────────
    def _draw(self, idx: int, pd: PointData):
        if self.point_items[idx]:
            self.scene().removeItem(self.point_items[idx])

        if pd.is_null:
            return

        if pd.visible:
            ellipse = self.scene().addEllipse(pd.x - config.MARK_RADIUS, pd.y - config.MARK_RADIUS,
                                              config.MARK_RADIUS * 2, config.MARK_RADIUS * 2,
                                              config.PEN, config.BRUSH)
            group = self.scene().createItemGroup([ellipse])
        else:
            l1 = self.scene().addLine(pd.x - config.MARK_RADIUS, pd.y - config.MARK_RADIUS,
                                      pd.x + config.MARK_RADIUS, pd.y + config.MARK_RADIUS, config.PEN)
            l2 = self.scene().addLine(pd.x - config.MARK_RADIUS, pd.y + config.MARK_RADIUS,
                                      pd.x + config.MARK_RADIUS, pd.y - config.MARK_RADIUS, config.PEN)
            group = self.scene().createItemGroup([l1, l2])

        group.setZValue(1)
        group.setData(0, idx)
        self.point_items[idx] = group
        if idx == self._selected_idx:
            self._set_group_pen(idx, self._highlight_pen)

    def _remove(self, idx: int):
        if self.point_items[idx]:
            self.scene().removeItem(self.point_items[idx])
            self.point_items[idx] = None
            if idx == self._selected_idx:
                self._selected_idx = None

    # ── 私用：彈出 0‥31 ID 選單，回傳被選 ID 或 None ─────────────
    def _popup_id_menu(self, global_pos):
        menu = QMenu(self)
        for idx in range(config.MAX_POINTS):
            act = menu.addAction(f"ID {idx + 1}")
            act.setData(idx)  # 用 QAction.data() 存 idx
            if idx == self._mw.active_idx:  # 目前那個打勾
                act.setCheckable(True)
                act.setChecked(True)
        chosen: QAction | None = menu.exec(global_pos)
        return chosen.data() if chosen else None

        # ── 私用：共用的「以 idx 在 scene_pos 標點」邏輯 ────────────
    def _mark_point(self, idx: int, scene_pos: QPointF):
        pd = PointData(scene_pos.x(), scene_pos.y())
        self._mw.set_point(idx, pd)  # 寫回資料
        self._draw(idx, pd)  # 畫點
        self.update_edges_for(idx)  # 更新線
        self._mw.select_row(idx)  # 表格同步
        self.highlight(idx)  # 黃框同步
        self._mw.select_next_row()  # 順手跳下一列

    # ── 更新邊 ───────────────────────────────────────────────────────
    def update_edges_for(self, point_idx: int):
        """只更新與 point_idx 有關的線段。"""
        for p1, p2, color in config.EDGES:
            # 只處理跟指定點有關的邊
            if point_idx not in (p1 - 1, p2 - 1):
                continue

            key = tuple(sorted((p1 - 1, p2 - 1)))
            item = self.edge_items.get(key)

            pd1 = self._mw.points[p1 - 1]
            pd2 = self._mw.points[p2 - 1]

            if pd1 and not pd1.is_null and pd2 and not pd2.is_null:
                # 兩端都有效 → 畫 / 更新
                if item is None:
                    item = self.scene().addLine(pd1.x, pd1.y, pd2.x, pd2.y,
                                                config.PENS[color])
                    item.setZValue(0)
                    self.edge_items[key] = item
                else:
                    item.setPen(config.PENS[color])
                    item.setLine(pd1.x, pd1.y, pd2.x, pd2.y)
            else:
                # 至少一端無效 → 刪掉
                if item is not None:
                    self.scene().removeItem(item)
                    del self.edge_items[key]
