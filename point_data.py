from dataclasses import dataclass


@dataclass
class PointData:
    x: float
    y: float
    visible: bool = True   # True: 圓點, False: X
    is_null: bool = False  # True: 不顯示