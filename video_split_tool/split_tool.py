#!/usr/bin/env python3
"""video_frame_extractor.py – PyQt6 GUI tool to list videos and split them into frames

Features
========
* Recursively scans a chosen root folder for video files (mp4/avi/mov/mkv).
* Displays a table with **Video Name | Duration (HH:MM:SS) | Total Frames | FPS**.
* Lets you select any row and specify how many frames **per second** to extract.
* The **Extract** button now shows the *expected* number of output images: «拆分所選影片 (產生 N 張照片)».
* Extracted frames are saved under a sibling directory named `<video_name>_frames` next to the original video.

Run with: ``python video_frame_extractor.py``  (Python ≥ 3.9, PyQt6, OpenCV‑Python).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Tuple

import cv2
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
    QMessageBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}


def hhmmss(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class VideoFrameExtractor(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video‑to‑Frames Tool")
        self.resize(1000, 600)

        # ── Widgets ───────────────────────────────────────────────────────────
        self.btn_choose_root = QPushButton("選擇資料夾並掃描影片…")
        self.btn_extract = QPushButton("拆分所選影片")
        self.btn_extract.setEnabled(False)

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 120)
        self.spin_fps.setValue(5)
        self.lbl_fps = QLabel("每秒擷取幾幀：")

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["影片名稱", "時間", "總 Frames", "FPS"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        # ── Layout ────────────────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.addWidget(self.btn_choose_root)
        top_bar.addStretch()
        top_bar.addWidget(self.lbl_fps)
        top_bar.addWidget(self.spin_fps)
        top_bar.addWidget(self.btn_extract)

        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.addLayout(top_bar)
        vbox.addWidget(self.table)
        vbox.addWidget(self.progress)
        self.setCentralWidget(central)

        # ── Signals ───────────────────────────────────────────────────────────
        self.btn_choose_root.clicked.connect(self._choose_and_scan)
        self.btn_extract.clicked.connect(self._extract_selected)
        self.table.itemSelectionChanged.connect(self._update_extract_button)
        self.spin_fps.valueChanged.connect(self._update_extract_button)

        # internal
        self._video_paths: list[Path] = []  # parallel to table rows

    # ───────────────────────────────────────────────────────────────────────
    # Scanning utilities
    # ───────────────────────────────────────────────────────────────────────

    def _choose_and_scan(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇包含影片的根資料夾")
        if folder:
            self._scan_videos(Path(folder))

    def _scan_videos(self, root: Path) -> None:
        self.table.setRowCount(0)
        self._video_paths.clear()
        for path in sorted(self._iter_videos(root)):
            info = self._probe_video(path)
            if info is None:
                continue
            duration, frames, fps = info
            self._append_row(path, hhmmss(duration), frames, f"{fps:.2f}")
        self.table.resizeColumnsToContents()
        self._update_extract_button()

    @staticmethod
    def _iter_videos(root: Path) -> Iterable[Path]:
        for p in root.rglob("*"):
            if p.suffix.lower() in VIDEO_EXTS and p.is_file():
                yield p

    @staticmethod
    def _probe_video(path: Path) -> Tuple[float, int, float] | None:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps else 0.0
        cap.release()
        return duration, frame_count, fps

    def _append_row(self, path: Path, dur: str, frames: int, fps: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, text in enumerate([path.name, dur, str(frames), fps]):
            item = QTableWidgetItem(text)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.table.setItem(row, col, item)
        self._video_paths.append(path)

    # ───────────────────────────────────────────────────────────────────────
    # UI Helpers
    # ───────────────────────────────────────────────────────────────────────

    def _update_extract_button(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            self.btn_extract.setEnabled(False)
            self.btn_extract.setText("拆分所選影片")
            return

        row = sel[0].row()
        total_frames = int(self.table.item(row, 2).text())
        vid_fps = float(self.table.item(row, 3).text())
        target_fps = self.spin_fps.value()
        interval = max(1, int(round(vid_fps / target_fps)))
        expected = total_frames // interval
        self.btn_extract.setEnabled(True)
        self.btn_extract.setText(f"拆分所選影片 (產生 {expected} 張照片)")

    # ───────────────────────────────────────────────────────────────────────
    # Extraction
    # ───────────────────────────────────────────────────────────────────────

    def _extract_selected(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return
        row = sel[0].row()
        video_path = self._video_paths[row]
        target_fps = self.spin_fps.value()
        self._extract_frames(video_path, target_fps)
        self._update_extract_button()  # refresh label with new selection / counts

    def _extract_frames(self, video_path: Path, target_fps: int):
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            QMessageBox.warning(self, "錯誤", f"無法開啟影片：{video_path}")
            return
        vid_fps = cap.get(cv2.CAP_PROP_FPS)
        if vid_fps == 0:
            QMessageBox.warning(self, "錯誤", "讀取不到 FPS。")
            cap.release()
            return
        interval = max(1, int(round(vid_fps / target_fps)))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out_dir = video_path.parent / f"{video_path.stem}_frames"
        out_dir.mkdir(exist_ok=True)

        self.progress.setMaximum(total_frames)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        saved = 0
        idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % interval == 0:
                out_name = out_dir / f"{video_path.stem}_{saved:06d}.jpg"
                cv2.imwrite(str(out_name), frame)
                saved += 1
            idx += 1
            if idx % 5 == 0:
                self.progress.setValue(idx)
                QApplication.processEvents()

        cap.release()
        self.progress.setVisible(False)
        QMessageBox.information(self, "完成", f"已擷取 {saved} 幀至 {out_dir}。")


# ─────────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    window = VideoFrameExtractor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
