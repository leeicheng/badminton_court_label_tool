# train_and_validate_pose.py
# -------------------------------------------------------------
# 一條龍：微調 → 驗證 → 產出預覽圖片
# pip install ultralytics pillow
# -------------------------------------------------------------
from ultralytics import YOLO
from pathlib import Path

DATA_YAML   = "dataset_output/dataset.yaml"   # GUI 產生的
PRETRAIN_PT = "yolov8n-pose.pt"               # 也可換 s/m/l
OUT_PROJ    = "runs"                          # Ultralytics 既定資料夾
EXP_NAME    = "pose_train"                    # ＝ runs/pose_train/
IMG_SIZE    = 640

def main():
    # 1. 讀預訓練模型
    model = YOLO(PRETRAIN_PT)

    # 2. Train（自帶每 epoch 的 val）
    model.train(
        data=DATA_YAML,
        epochs=100,
        imgsz=IMG_SIZE,
        batch=16,
        project=OUT_PROJ,
        name=EXP_NAME,
        exist_ok=True,
        workers=4,
    )

    # 3. 針對最終 best.pt 做一次完整驗證，並存 COCO-style json
    #    split='val' → 只跑 data.yaml 裡定義的 val
    metrics = model.val(
        data=DATA_YAML,
        split="val",
        imgsz=IMG_SIZE,
        save_json=True,      # 會輸出 val_predictions.json
        project=OUT_PROJ,
        name=f"{EXP_NAME}_val",
        exist_ok=True,
    )

    # 印主要指標，自己想看更多就 print(metrics) 全丟
    print("== Val Metrics ==")
    for k, v in metrics.results_dict.items():
        print(f"{k:<20}: {v:.4f}")

    # 4. 隨手把驗證集所有圖做推論＋繪圖存檔，方便肉眼檢
    #    存到 runs/val_preview/images
    model.predict(
        source="dataset_output/val/images",
        imgsz=IMG_SIZE,
        conf=0.25,
        save=True,          # 會在 project/name 下產生 images/
        project=OUT_PROJ,
        name="val_preview",
        exist_ok=True,
    )

    print("\n✅  完成！")
    print(f"• best.pt      → {Path(OUT_PROJ) / EXP_NAME / 'weights/best.pt'}")
    print(f"• val 指標 json → {Path(OUT_PROJ) / (EXP_NAME + '_val')}")
    print(f"• 預覽圖片      → {Path(OUT_PROJ) / 'val_preview' / 'images'}")

if __name__ == "__main__":
    main()
