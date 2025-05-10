import json
from pathlib import Path
from dataclasses import asdict
from typing import List, Optional
from PyQt6.QtCore import QRectF
from point_data import PointData
from config import MAX_POINTS, POINT_FILE_SUFFIX

def pts_path(img_path: str) -> Path:
    return Path(img_path + POINT_FILE_SUFFIX)

def save(label_path: Path,
         points: List[Optional[PointData]],
         bboxes) -> None:
    pts_out = [
        asdict(p) if p and not p.is_null else
        {"x": 0, "y": 0, "visible": False, "is_null": True}
        for p in points
    ]
    bboxes_out = [
        {"x": r.x(), "y": r.y(),
         "w": r.width(), "h": r.height()}
        for r in bboxes
    ]
    json.dump({"points": pts_out, "bboxes": bboxes_out},
              open(label_path, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

def load(label_path: Path):
    """回傳 (points_list, bbox_rectf_list)"""
    from PyQt6.QtCore import QRectF   # 避免循環 import
    pts = [None] * MAX_POINTS
    bbs = []

    if not label_path.exists():
        return pts, bbs

    raw = json.load(open(label_path, "r", encoding="utf-8"))
    if isinstance(raw, list):              # 舊格式
        raw = {"points": raw, "bboxes": []}

    for idx, data in enumerate(raw.get("points", [])):
        if 0 <= idx < MAX_POINTS and not data.get("is_null", False):
            pts[idx] = PointData(**data)

    for b in raw.get("bboxes", []):
        bbs.append(QRectF(b["x"], b["y"], b["w"], b["h"]))

    return pts, bbs
