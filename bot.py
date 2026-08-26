import os
import pickle
import zipfile
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
TOKEN = "8216393055:AAF6sbjxic7y9tpMN-yKGTNagAEqnszhL8U"
PHOTO_DB_URL = "https://dl.dropboxusercontent.com/scl/fi/xxl7bna8h3re0ks9jdsy6/photo_db.zip?rlkey=j94j0yuv1e3sg67txyzda4zo9&dl=1"
INDEX_PATH = "faiss_index.bin"
PATHS_PATH = "image_paths.pkl"
MODEL_PATH = "best.pt"  # используем обученную модель

CATEGORY_MAP = {
    "01_otsutstvuyut_birki": "⚠️ Отсутствуют бирки на оборудовании",
    "02_zadelka_prohodok": "⚠️ Не выполнена заделка проходок",
    "03_zazemlenie_ne_vypolneno": "⚠️ Не выполнено заземление",
    "04_shpilki_lotka_ne_srezany": "⚠️ Шпильки лотка не срезаны",
}

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

    if not os.path.exists("photo_db"):
        for item in os.listdir("."):
            if os.path.isdir(item) and item.startswith("photo_db"):
                os.rename(item, "photo_db")
                break
        else:
            os.mkdir("photo_db")
            for f in os.listdir("."):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    os.rename(f, os.path.join("photo_db", f))

    print(f"✅ photo_db готова, файлов: {len(os.listdir('photo_db'))}")

# ===== ЗАГРУЗКА ИНДЕКСА =====
def load_index():
    global index, image_paths
    if index is None:
        print("Загружаю индекс...")
        index = faiss.read_index(INDEX_PATH)
        with open(PATHS_PATH, "rb") as f:
            raw_paths = pickle.load(f)
        image_paths = [os.path.join("photo_db", os.path.basename(p)) for p in raw_paths]
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

def get_category(filename):
    for prefix, text in CATEGORY_MAP.items():
        if filename.startswith(prefix):
            return text
    return "📌 Замечание не распознано"

# ===== ОБРАБОТЧИК (всегда выдаёт замечание) =====
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
        distances, indices = index.search(emb, 1)  # ищем только одно самое похожее

        if len(indices[0]) == 0 or indices[0][0] == -1:
            await update.message.reply_text("❌ Не удалось найти похожее изображение.")
            return

        idx = indices[0][0]
        similarity = 1 / (1 + distances[0][0])
        similarity_percent = similarity * 100

        filename = os.path.basename(image_paths[idx])
        category_text = get_category(filename)

        response = (
            f"🔍 **Найдено замечание:**\n"
            f"{category_text}\n\n"
            f"📊 Схожесть: {similarity_percent:.1f}%\n"
            f"📄 Образец: {filename}"
        )
        await update.message.reply_text(response)

    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    download_and_extract_photos()
    load_index()
    load_model()

    app = Application.builder().token(TOKEN).read_timeout(60).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("🚀 Бот запущен. Ожидаю фото...")
    app.run_polling()