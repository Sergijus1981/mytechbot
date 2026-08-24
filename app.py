import os
import tempfile
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from PIL import Image
import imagehash

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен!")

def get_phash(file_path):
    """Вычисляет перцептивный хеш изображения."""
    try:
        with Image.open(file_path) as img:
            # Приводим к одному размеру для стабильности
            img = img.resize((128, 128))
            return imagehash.phash(img)
    except Exception as e:
        logging.error(f"Ошибка при вычислении хеша: {e}")
        return None

def load_reference_hashes(photos_dir='.'):
    """Загружает хеши всех изображений в подпапках."""
    ref_hashes = {}
    for category in os.listdir(photos_dir):
        cat_path = os.path.join(photos_dir, category)
        if os.path.isdir(cat_path) and not category.startswith('.') and category not in ('__pycache__', '.git'):
            ref_hashes[category] = []
            for fname in os.listdir(cat_path):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    full_path = os.path.join(cat_path, fname)
                    h = get_phash(full_path)
                    if h is not None:
                        ref_hashes[category].append(h)
    return ref_hashes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_HASHES = load_reference_hashes(os.path.join(BASE_DIR, '.'))

print(f"Загружено категорий: {len(REF_HASHES)}")
for cat, hashes in REF_HASHES.items():
    print(f"{cat}: {len(hashes)} хешей")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            temp_path = tmp.name
        await file.download_to_drive(temp_path)
        user_hash = get_phash(temp_path)
        os.remove(temp_path)

        if user_hash is None:
            await update.message.reply_text('Не удалось обработать фото.')
            return

        # Порог схожести (0 — идентичны, чем меньше, тем лучше)
        THRESHOLD = 10  # для pHash 64 бита — 10 — хороший допуск
        best_category = None
        best_diff = None

        for category, hashes in REF_HASHES.items():
            for ref_hash in hashes:
                diff = user_hash - ref_hash  # расстояние Хэмминга
                if diff < THRESHOLD:
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_category = category

        if best_category:
            await update.message.reply_text(f'Найдено совпадение: {best_category} (расхождение {best_diff})')
        else:
            await update.message.reply_text('Не найдено совпадений.')
    except Exception as e:
        logging.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text('Произошла ошибка при обработке фото.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Бот запущен и слушает...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
