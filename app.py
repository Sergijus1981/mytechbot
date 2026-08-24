import os
import hashlib
import tempfile
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен!")

def get_md5(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def load_reference_hashes(photos_dir='.'):
    ref_hashes = {}
    for category in os.listdir(photos_dir):
        cat_path = os.path.join(photos_dir, category)
        if os.path.isdir(cat_path) and not category.startswith('.') and category not in ('__pycache__', '.git'):
            ref_hashes[category] = []
            for fname in os.listdir(cat_path):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    full_path = os.path.join(cat_path, fname)
                    try:
                        ref_hashes[category].append(get_md5(full_path))
                    except Exception:
                        continue
    return ref_hashes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_HASHES = load_reference_hashes(os.path.join(BASE_DIR, '.'))

print(f"Загружено категорий: {len(REF_HASHES)}")
for cat, hashes in REF_HASHES.items():
    print(f"{cat}: {len(hashes)} хешей")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Отправь мне **файл** с изображением (не как фото, а как файл).')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Обрабатываем и фото, и документы
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        elif update.message.document and update.message.document.mime_type.startswith('image/'):
            file = await update.message.document.get_file()
        else:
            await update.message.reply_text('Пожалуйста, отправь изображение как файл или как фото.')
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            temp_path = tmp.name
        await file.download_to_drive(temp_path)
        user_hash = get_md5(temp_path)
        os.remove(temp_path)

        for category, hashes in REF_HASHES.items():
            if user_hash in hashes:
                await update.message.reply_text(f'✅ Найдено совпадение: {category}')
                return

        await update.message.reply_text('❌ Не найдено совпадений.')
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text('Произошла ошибка при обработке.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_photo))  # обрабатываем и документы-картинки
    print("Бот запущен и слушает...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
