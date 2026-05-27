import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import imagehash
import glob

# ===== НАСТРОЙКИ =====
TOKEN = "8917838537:AAHm8tzHuNRbX5_CaRNKxqQl9o_Nj-p7U1E"   # Замени на токен от @BotFather

# Папка с твоими фотографиями (внутри неё должны быть подпапки с названиями замечаний)
BASE_DIR = r"C:\Users\ЗС\OneDrive\Desktop\MyTechBot\photos"

# ===== ЗАГРУЗКА ЭТАЛОННЫХ ФОТО =====
reference_hashes = []  # список из (хэш, описание_нарушения, путь_к_фото)

for subdir in os.listdir(BASE_DIR):
    subdir_path = os.path.join(BASE_DIR, subdir)
    if not os.path.isdir(subdir_path):
        continue
    # название подпапки — это и есть текст замечания
    comment = subdir
    # ищем все .jpg и .png
    for img_file in glob.glob(os.path.join(subdir_path, "*.jpg")) + glob.glob(os.path.join(subdir_path, "*.png")):
        try:
            img = Image.open(img_file)
            hash_val = imagehash.average_hash(img)
            reference_hashes.append((hash_val, comment, img_file))
            print(f"Загружено: {img_file} -> {comment}")
        except Exception as e:
            print(f"Ошибка с {img_file}: {e}")

logging.basicConfig(level=logging.INFO)

# ===== КОМАНДЫ БОТА =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришли мне фото, и я скажу, на какое нарушение оно похоже.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    # берём самое большое фото
    photo_file = await update.message.photo[-1].get_file()
    temp_path = "temp_img.jpg"
    await photo_file.download_to_drive(temp_path)

    # вычисляем хэш присланного фото
    img = Image.open(temp_path)
    query_hash = imagehash.average_hash(img)

    # ищем минимальное расстояние
    best_match = None
    best_distance = 64  # максимальное возможное
    for ref_hash, comment, path in reference_hashes:
        dist = query_hash - ref_hash
        if dist < best_distance:
            best_distance = dist
            best_match = (comment, dist, path)

    os.remove(temp_path)

    if best_match and best_distance < 10:
        await update.message.reply_text(
            f"🔍 Похоже на нарушение:\n<b>{best_match[0]}</b>\n"
            f"📊 Схожесть: {best_match[1]} (0 = идеально)\n"
            f"📁 Эталонное фото: {best_match[2]}",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Не удалось распознать нарушение.\nПопробуй другое фото или добавь больше примеров.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ Бот запущен и слушает сообщения...")
    app.run_polling()

if __name__ == "__main__":
    main()