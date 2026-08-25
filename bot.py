import os
import pickle
import numpy as np
import faiss
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from PIL import Image
import torch
from torchvision import transforms
from ultralytics import YOLO

# ===== НАСТРОЙКИ =====
TOKEN = "8917838537:AAHm8tzHuNRbX5_CaRNKxqQl9o_Nj-p7U1E"  # ЗАМЕНИ НА СВОЙ ТОКЕН
YANDEX_URL = "https://disk.hexed.pw/d/I0VHR1A8_8PnJA"  # твоя ссылка
MODEL_PATH = r"C:\Users\ЗС\OneDrive\Desktop\TechBotFinal\yolov8n-cls.pt"  # или путь к best.pt, если хочешь
INDEX_PATH = "faiss_index.bin"
PATHS_PATH = "image_paths.pkl"
PHOTO_DB_DIR = "photo_db"

# ===== ФУНКЦИЯ СКАЧИВАНИЯ =====
def download_photos():
    if os.path.exists(PHOTO_DB_DIR) and len(os.listdir(PHOTO_DB_DIR)) > 0:
        print("📁 photo_db уже существует, пропускаю загрузку.")
        return

    print("📥 Скачиваю фото с Яндекс.Диска...")
    try:
        subprocess.run([
            "ydisk-downloader", "download", YANDEX_URL, "."
        ], check=True)
        print("✅ Фото скачаны.")
    except Exception as e:
        print(f"❌ Ошибка скачивания: {e}")
        raise

# ===== ФУНКЦИЯ ИНДЕКСАЦИИ =====
def build_index():
    if os.path.exists(INDEX_PATH) and os.path.exists(PATHS_PATH):
        print("📂 Индекс уже существует, пропускаю.")
        return

    print("🔄 Строю индекс заново...")
    # Загружаем модель
    model = YOLO(MODEL_PATH)
    torch_model = model.model.model
    embedder = torch.nn.Sequential(*list(torch_model.children())[:-1])
    embedder.eval()
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    def get_embedding(image_path):
        img = Image.open(image_path).convert('RGB')
        img_tensor = transform(img).unsqueeze(0)
        with torch.no_grad():
            emb = embedder(img_tensor).flatten().cpu().numpy()
        return emb

    from pathlib import Path
    image_paths = list(Path(PHOTO_DB_DIR).glob("*.jpg")) + \
                  list(Path(PHOTO_DB_DIR).glob("*.jpeg")) + \
                  list(Path(PHOTO_DB_DIR).glob("*.png"))
    if not image_paths:
        raise Exception("Нет изображений в photo_db")

    embeddings = []
    valid_paths = []
    for img_path in image_paths:
        emb = get_embedding(str(img_path))
        if emb is not None:
            embeddings.append(emb)
            valid_paths.append(str(img_path))

    embeddings = np.array(embeddings).astype('float32')
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)
    with open(PATHS_PATH, "wb") as f:
        pickle.dump(valid_paths, f)
    print(f"✅ Индекс сохранён, {len(valid_paths)} изображений.")

# ===== ЗАГРУЗКА ИНДЕКСА ДЛЯ БОТА =====
print("Загружаю индекс...")
index = faiss.read_index(INDEX_PATH)
with open(PATHS_PATH, "rb") as f:
    image_paths = pickle.load(f)
print(f"Индекс загружен, {len(image_paths)} изображений.")

# ===== ОБРАБОТЧИК ФОТО =====
async def handle_photo(update: Update, context):
    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        user_path = f"temp_{update.message.chat.id}.jpg"
        await file.download_to_drive(user_path)

        # Получаем эмбеддинг (используем ту же модель, что и при индексации)
        model = YOLO(MODEL_PATH)
        torch_model = model.model.model
        embedder = torch.nn.Sequential(*list(torch_model.children())[:-1])
        embedder.eval()
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        def get_embedding(image_path):
            img = Image.open(image_path).convert('RGB')
            img_tensor = transform(img).unsqueeze(0)
            with torch.no_grad():
                emb = embedder(img_tensor).flatten().cpu().numpy()
            return emb

        emb = get_embedding(user_path)
        os.remove(user_path)

        emb = np.array([emb]).astype('float32')
        k = 5
        distances, indices = index.search(emb, k)

        if len(indices[0]) == 0:
            await update.message.reply_text("Индекс пуст.")
            return

        await update.message.reply_text(f"🔍 Нашёл {len(indices[0])} похожих фото:")

        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            sim = 1 / (1 + distances[0][i])
            caption = f"#{i+1} Схожесть: {sim*100:.1f}%"
            with open(image_paths[idx], 'rb') as f:
                await update.message.reply_photo(photo=f, caption=caption)

    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text(f"Ошибка: {e}")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    # Шаг 1: скачиваем фото, если их нет
    download_photos()

    # Шаг 2: строим индекс, если его нет
    build_index()

    # Шаг 3: запускаем бота
    app = Application.builder().token(TOKEN).read_timeout(60).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("🚀 Бот запущен. Ожидаю фото...")
    app.run_polling()