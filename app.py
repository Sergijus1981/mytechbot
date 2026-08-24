import os
import hashlib
import tempfile
import logging
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

# Логирование
logging.basicConfig(level=logging.INFO)

# Токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен!")

def get_md5(file_path):
    """Вычисляет MD5-хеш файла."""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

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
    """Обработчик команды /start."""
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик полученных фото."""
    try:
        file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            temp_path = tmp.name
        await file.download_to_drive(temp_path)
        user_hash = get_md5(temp_path)
        os.remove(temp_path)

        for category, hashes in REF_HASHES.items():
            if user_hash in hashes:
                await update.message.reply_text(f'Найдено совпадение: {category}')
                return

        await update.message.reply_text('Не найдено совпадений.')
    except Exception as e:
        logging.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text('Произошла ошибка при обработке фото.')

async def main():
    """Главная функция запуска бота."""
    app = Application.builder().token(TOKEN).build()
    # Принудительно удаляем вебхук, чтобы избежать конфликтов
    await app.bot.delete_webhook(drop_pending_updates=True)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Бот запущен и слушает...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
