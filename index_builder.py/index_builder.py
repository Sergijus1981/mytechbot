import os
import numpy as np
import faiss
import pickle
from pathlib import Path
from ultralytics import YOLO

# ===== НАСТРОЙ ПУТИ =====
# Путь к твоей папке с эталонными фото (замени на свой)
DB_PATH = r"C:\Users\ЗС\OneDrive\Desktop\TechBotFinal\photo_db"   # <--- СЮДА ТВОЯ ПАПКА

# Путь к обученной модели (у тебя лежит в runs)
MODEL_PATH = r"C:\Users\ЗС\OneDrive\Desktop\TechBotFinal\runs\best.pt"  # или .pt файл

# ===== ЗАГРУЗКА МОДЕЛИ =====
if not os.path.exists(MODEL_PATH):
    print("Модель не найдена! Использую базовую yolov8n-cls.pt")
    model = YOLO("yolov8n-cls.pt")
else:
    model = YOLO(MODEL_PATH)

def get_embedding(image_path):
    try:
        results = model.predict(source=image_path, embed=True, verbose=False)
        if results and results[0].embeds is not None:
            emb = results[0].embeds[0].cpu().numpy()
            return emb
        else:
            return None
    except Exception as e:
        print(f"Ошибка при обработке {image_path}: {e}")
        return None

# ===== ИНДЕКСАЦИЯ =====
# Собираем все картинки из папки (поддерживаемые форматы)
image_paths = list(Path(DB_PATH).glob("*.jpg")) + \
              list(Path(DB_PATH).glob("*.jpeg")) + \
              list(Path(DB_PATH).glob("*.png"))

if not image_paths:
    print(f"В папке {DB_PATH} не найдено изображений!")
    exit()

print(f"Найдено {len(image_paths)} изображений. Начинаю индексацию...")

embeddings = []
valid_paths = []

for i, img_path in enumerate(image_paths):
    print(f"Обработка {i+1}/{len(image_paths)}: {img_path.name}")
    emb = get_embedding(str(img_path))
    if emb is not None:
        embeddings.append(emb)
        valid_paths.append(str(img_path))
    else:
        print(f"  пропущено")

if not embeddings:
    print("Не удалось получить ни одного эмбеддинга. Проверь модель.")
    exit()

embeddings = np.array(embeddings).astype('float32')
dim = embeddings.shape[1]

# Создаём FAISS индекс
index = faiss.IndexFlatL2(dim)
index.add(embeddings)

# Сохраняем индекс и список путей
faiss.write_index(index, "faiss_index.bin")
with open("image_paths.pkl", "wb") as f:
    pickle.dump(valid_paths, f)

print(f"Готово! Индекс сохранён в faiss_index.bin")
print(f"Всего занесено {len(valid_paths)} изображений.")