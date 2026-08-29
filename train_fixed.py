from ultralytics import YOLO

# ===== НАСТРОЙКИ =====
DATA_PATH = "dataset_split"   # твой датасет (должен быть в этой же папке)
MODEL_NAME = "yolov8n-cls.pt"
EPOCHS = 50
IMAGE_SIZE = 224
BATCH_SIZE = 16

def main():
    print(f"Загружаю модель {MODEL_NAME}...")
    model = YOLO(MODEL_NAME)
    
    print("Начинаю обучение...")
    results = model.train(
        data=DATA_PATH,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        device="cpu",           # поставь "0", если есть GPU
        workers=4,
        seed=42,
        deterministic=True,
        plots=True
    )
    
    print("Обучение завершено!")
    print(f"Логи сохранены в {results.save_dir}")
    print("✅ Модель готова. Найди best.pt в папке runs/classify/.../weights/")

if __name__ == "__main__":
    main()