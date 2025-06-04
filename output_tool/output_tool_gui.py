# yolo_dataset_tool.py – PyQt6 GUI 產生 YOLOv8 Keypoint Dataset（自動縮放 640×640 + 預覽圖）
# ---------------------------------------------------------------------
#  功能：
#  1. 選擇含 image + 同名 *.points.json 的根資料夾
#  2. 依 Train / Val / Test 百分比分配，輸出到 dataset_output/{split}/{images|labels}
#  3. 影像統一縮放為 640×640，bbox 與 32 個 keypoints 同步縮放
#  4. 轉 YOLOv8 keypoint label：cls xc yc w h x1 y1 v1 … x32 y32 v32（座標皆 0~1）
#     is_null → xy=0, v=0；visible=True → v=2；visible=False → v=1
#  5. 產生 dataset.yaml（含 kpt_shape）
#  6. 額外產生 preview 圖：dataset_output/preview/<filename>_preview.jpg 方便人工檢查
# ---------------------------------------------------------------------
# 依賴：PyQt6, pillow
# pip install PyQt6 pillow
from __future__ import annotations
import sys, json, random, shutil, textwrap
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QLabel,
    QPushButton, QHBoxLayout, QVBoxLayout, QSpinBox, QMessageBox, QLineEdit
)

IMG_EXTS = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tif', '*.tiff')
CLASS_ID = 0
CLASS_NAMES = ['object']
OUTPUT_SIZE = 640  # 640×640
KPT_NUM = 32

# ---------- 掃描 ----------

def load_pairs(root: Path) -> List[Tuple[Path, Path]]:
    pairs = []
    for pattern in IMG_EXTS:
        for img_path in root.rglob(pattern):
            json_path = img_path.with_suffix(img_path.suffix + '.points.json')
            if json_path.exists():
                pairs.append((img_path, json_path))
    return pairs

# ---------- 標籤 ----------

def build_label(data: dict, scale_x: float, scale_y: float) -> str:
    bb = data['bboxes'][0]
    x = bb['x'] * scale_x
    y = bb['y'] * scale_y
    w = bb['w'] * scale_x
    h = bb['h'] * scale_y
    xc = (x + w * 0.5) / OUTPUT_SIZE
    yc = (y + h * 0.5) / OUTPUT_SIZE
    bw = w / OUTPUT_SIZE
    bh = h / OUTPUT_SIZE

    kpts = []
    for p in data['points']:
        if p.get('is_null'):
            kpts.extend([0, 0, 0])
        else:
            kx_pix = p['x'] * scale_x
            ky_pix = p['y'] * scale_y
            kx = kx_pix / OUTPUT_SIZE
            ky = ky_pix / OUTPUT_SIZE
            vflag = 2 if p.get('visible', True) else 1
            kpts.extend([kx, ky, vflag])
    while len(kpts) < KPT_NUM * 3:
        kpts.extend([0, 0, 0])
    values = [CLASS_ID, xc, yc, bw, bh] + kpts
    return ' '.join(f"{v:.6f}" if isinstance(v, float) else str(v) for v in values)

# ---------- 預覽 ----------

def save_preview(dst_img: Path, data: dict, scale_x: float, scale_y: float, preview_dir: Path):
    im = Image.open(dst_img).convert('RGB')
    draw = ImageDraw.Draw(im)
    # bbox
    bb = data['bboxes'][0]
    x1 = bb['x'] * scale_x
    y1 = bb['y'] * scale_y
    x2 = x1 + bb['w'] * scale_x
    y2 = y1 + bb['h'] * scale_y
    draw.rectangle([x1, y1, x2, y2], outline='red', width=2)
    # keypoints
    r = 3
    for idx, p in enumerate(data['points']):
        if p.get('is_null'):
            continue
        cx = p['x'] * scale_x
        cy = p['y'] * scale_y
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline='yellow', width=2)
        # 也可以編號： draw.text((cx+4, cy), str(idx), fill='yellow')
    preview_dir.mkdir(parents=True, exist_ok=True)
    im.save(preview_dir / f"{dst_img.stem}_preview.jpg")

# ---------- YAML ----------

def write_yaml(out_root: Path):
    yaml_text = textwrap.dedent(f"""\
        path: {out_root}
        train: train/images
        val: val/images
        test: test/images
        names: {CLASS_NAMES}
        kpt_shape: [{KPT_NUM}, 3]
    """)
    (out_root / 'dataset.yaml').write_text(yaml_text)

# ---------- GUI ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('YOLOv8 Keypoint Dataset Builder')
        self.resize(680, 240)
        central = QWidget(); self.setCentralWidget(central)
        v = QVBoxLayout(central)

        r1 = QHBoxLayout()
        self.le_path = QLineEdit(); self.le_path.setReadOnly(True)
        btn_browse = QPushButton('Browse…'); btn_browse.clicked.connect(self.browse)
        r1.addWidget(QLabel('Root folder:')); r1.addWidget(self.le_path, 1); r1.addWidget(btn_browse)
        v.addLayout(r1)

        r2 = QHBoxLayout()
        self.sb_train = QSpinBox(); self.sb_train.setRange(0,100); self.sb_train.setValue(70)
        self.sb_val = QSpinBox(); self.sb_val.setRange(0,100); self.sb_val.setValue(20)
        self.sb_test = QSpinBox(); self.sb_test.setRange(0,100); self.sb_test.setValue(10)
        r2.addWidget(QLabel('Train %')); r2.addWidget(self.sb_train)
        r2.addWidget(QLabel('Val %'));   r2.addWidget(self.sb_val)
        r2.addWidget(QLabel('Test %'));  r2.addWidget(self.sb_test)
        v.addLayout(r2)

        btn_gen = QPushButton('Generate Dataset'); btn_gen.clicked.connect(self.generate)
        v.addWidget(btn_gen)

    # ---- slots ----
    def browse(self):
        p = QFileDialog.getExistingDirectory(self, 'Select Root Folder')
        if p:
            self.le_path.setText(p)

    def generate(self):
        root = Path(self.le_path.text())
        if not root.is_dir():
            QMessageBox.warning(self, 'Error', 'Select a valid folder'); return
        t,vv,s = self.sb_train.value(), self.sb_val.value(), self.sb_test.value()
        if t+vv+s!=100:
            QMessageBox.warning(self, 'Error', 'Ratios must sum to 100'); return
        pairs = load_pairs(root)
        if not pairs:
            QMessageBox.warning(self, 'Error', 'No image/json pairs found'); return
        random.shuffle(pairs)
        n=len(pairs); n_train=int(n*t/100); n_val=int(n*vv/100)
        splits = {'train':pairs[:n_train],'val':pairs[n_train:n_train+n_val],'test':pairs[n_train+n_val:]}

        out_root = root/'dataset_output'
        if out_root.exists(): shutil.rmtree(out_root)
        preview_dir = out_root/'preview'

        for split,items in splits.items():
            img_dir = out_root/split/'images'
            lbl_dir = out_root/split/'labels'
            img_dir.mkdir(parents=True, exist_ok=True)
            lbl_dir.mkdir(parents=True, exist_ok=True)
            for img_path,json_path in items:
                data = json.loads(json_path.read_text())
                # 讀原圖 & 計算縮放
                with Image.open(img_path) as im:
                    orig_w,orig_h = im.size
                    scale_x = OUTPUT_SIZE/orig_w
                    scale_y = OUTPUT_SIZE/orig_h
                    im_resized = im.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.BILINEAR)
                    dst_img = img_dir / img_path.name
                    im_resized.save(dst_img)
                # 標籤
                label_line = build_label(data, scale_x, scale_y)
                (lbl_dir/(img_path.stem+'.txt')).write_text(label_line+'\n')
                # 預覽
                save_preview(dst_img, data, scale_x, scale_y, preview_dir)

        write_yaml(out_root)
        QMessageBox.information(self,'Done',f'Dataset created at: {out_root}')

# ---------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())