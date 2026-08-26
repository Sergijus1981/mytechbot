import os
import pickle
import zipfile
import requests
import gdown
import numpy as np
import faiss
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from PIL import Image
import torch
from torchvision import transforms
from ultralytics import YOLO

# ===== КОНФИГ =====
TOKEN = "8997588392:AAGYVTsjK0n9JYKMIYPTF-FAFhVhbUY1SzE"
PHOTO_DB_URL = "https://drive.google.com/uc?export=download&id=1oZwqT2bQRy5C17U0ZYc2cpvg37R461Y7"
INDEX_PATH = "faiss_index.bin"
PATHS_PATH = "image_paths.pkl"
MODEL_PATH = "yolov8n-cls.pt"
# Глобальные переменные
index = None
image_paths = None
embedder = None
transform = None

# ===== АВТОЗАГРУЗКА ФОТО =====
def download_and_extract_photos():
    if os.path.exists("photo_db") and len(os.listdir("photo_db")) > 0:
        print("📁 photo_db уже существует, пропускаю загрузку.")
        return

    print("📥 Скачиваю архив с фото через gdown...")
    gdown.download(PHOTO_DB_URL, "photo_db.zip", quiet=False)

    print("📦 Распаковываю...")
    with zipfile.ZipFile("photo_db.zip", "r") as zip_ref:
        zip_ref.extractall(".")
    os.remove("photo_db.zip")
    print("✅ Фото готовы.")

# ===== ПОСТРОЕНИЕ ИНДЕКСА =====
def build_index():
    if os.path.exists(INDEX_PATH) and os.path.exists(PATHS_PATH):
        print("📂 Индекс уже существует, пропускаю.")
        return

    print("🔨 Строю индекс...")
    import subprocess
    subprocess.run(["python", "index_builder.py"], check=True)
    print("✅ Индекс построен.")

# ===== ЗАГРУЗКА ИНДЕКСА =====
def load_index():
    global index, image_paths
    if index is None:
        print("Загружаю индекс...")
        index = faiss.read_index(INDEX_PATH)
        with open(PATHS_PATH, "rb") as f:
            image_paths = pickle.load(f)
        print(f"Индекс загружен, {len(image_paths)} изображений.")

# ===== ЗАГРУЗКА МОДЕЛИ =====
def load_model():
    global embedder, transform
    if embedder is None:
        print("Загружаю модель...")
        model = YOLO(MODEL_PATH)
        torch_model = model.model.model
        embedder = torch.nn.Sequential(*list(torch_model.children())[:-1])
        embedder.eval()
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        print("Модель загружена.")

def get_embedding(image_path):
    img = Image.open(image_path).convert('RGB')
    img_tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        emb = embedder(img_tensor).flatten().cpu().numpy()
    return emb

# ===== ОБРАБОТЧИК =====
async def handle_photo(update, context):
    try:
        load_index()
        load_model()
        photo = update.message.photo[-1]
        file = await photo.get_file()
        user_path = f"temp_{update.message.chat.id}.jpg"
        await file.download_to_drive(user_path)
        print(f"Получено фото от {update.message.chat.id}")

        emb = get_embedding(user_path)
        os.remove(user_path)

        emb = np.array([emb]).astype('float32')
        k = 5
        distances, indices = index.search(emb, k)

        if len(indices[0]) == 0 or indices[0][0] == -1:
            await update.message.reply_text("Похожих фото не найдено.")
            return

        await update.message.reply_text(f"🔍 Нашёл {len(indices[0])} похожих фото:")

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            sim = 1 / (1 + distances[0][i])
            caption = f"#{i+1} Схожесть: {sim*100:.1f}%"
            path = os.path.normpath(image_paths[idx])
            if not os.path.exists(path):
                await update.message.reply_text(f"❌ Файл {path} не найден на сервере!")
                continue
            with open(path, 'rb') as f:
                await update.message.reply_photo(photo=f, caption=caption)

    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text(f"Ошибка: {e}")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    download_and_extract_photos()
    build_index()
    load_index()
    load_model()

    app = Application.builder().token(TOKEN).read_timeout(60).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("🚀 Бот запущен. Ожидаю фото...")
    app.run_polling()
