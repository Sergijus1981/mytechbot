import os
import numpy as np
import faiss
import pickle
import torch
from pathlib import Path
from PIL import Image
from torchvision import transforms
from ultralytics import YOLO

# ===== НАСТРОЙКИ =====
DB_PATH = r"C:\Users\ЗС\OneDrive\Desktop\TechBotFinal\photo_db"
MODEL_PATH = r"C:\Users\ЗС\OneDrive\Desktop\TechBotFinal\yolov8n-cls.pt"
# ===== ЗАГРУЗКА МОДЕЛИ =====
print("Загружаем модель...")
model = YOLO(MODEL_PATH)

# Получаем PyTorch модель без последнего слоя (классификатора)
# Для YOLOv8-cls модель состоит из backbone и головы. Мы отрежем голову.
if hasattr(model, 'model') and hasattr(model.model, 'model'):
    # Для YOLOv8: model.model - это Sequential, последний слой - Linear
    # Убираем последний слой
    torch_model = model.model.model
    # Убираем последний слой (классификатор)
    embedder = torch.nn.Sequential(*list(torch_model.children())[:-1])
else:
    raise Exception("Не удалось извлечь PyTorch модель из YOLO")

embedder.eval()
print("Модель загружена.")

# ===== ТРАНСФОРМАЦИИ =====
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def get_embedding(image_path):
    try:
        img = Image.open(image_path).convert('RGB')
        img_tensor = transform(img).unsqueeze(0)  # добавляем batch
        with torch.no_grad():
            emb = embedder(img_tensor).flatten().cpu().numpy()
        return emb
    except Exception as e:
        print(f"Ошибка при обработке {image_path}: {e}")
        return None

# ===== ИНДЕКСАЦИЯ =====
print("Поиск изображений в папке:", DB_PATH)
image_paths = list(Path(DB_PATH).glob("*.jpg")) + \
              list(Path(DB_PATH).glob("*.jpeg")) + \
              list(Path(DB_PATH).glob("*.png"))

if not image_paths:
    print("В папке не найдено изображений!")
    exit(1)

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
    print("Не удалось получить ни одного эмбеддинга. Проверь модель и изображения.")
    exit(1)

embeddings = np.array(embeddings).astype('float32')
dim = embeddings.shape[1]

# Создаём FAISS индекс
index = faiss.IndexFlatL2(dim)
index.add(embeddings)

# Сохраняем
faiss.write_index(index, "faiss_index.bin")
with open("image_paths.pkl", "wb") as f:
    pickle.dump(valid_paths, f)

print(f"Готово! Индекс сохранён в faiss_index.bin")
print(f"Всего занесено {len(valid_paths)} изображений.")