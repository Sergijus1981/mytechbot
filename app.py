import os
import hashlib
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes

TOKEN = os.getenv('TELEGRAM_TOKEN')

# Функция для вычисления простого хеша изображения (MD5)
def get_image_hash(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

# Загружаем хеши всех эталонных фото при старте бота
def load_reference_hashes(photos_dir='photos'):
    ref_hashes = {}
    if not os.path.exists(photos_dir):
        return ref_hashes
    for category in os.listdir(photos_dir):
        cat_path = os.path.join(photos_dir, category)
        if os.path.isdir(cat_path):
            ref_hashes[category] = []
            for fname in os.listdir(cat_path):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    full_path = os.path.join(cat_path, fname)
                    ref_hashes[category].append(get_image_hash(full_path))
    return ref_hashes

REF_HASHES = load_reference_hashes()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем фото
    photo_file = await update.message.photo[-1].get_file()
    temp_path = f"/tmp/{photo_file.file_id}.jpg"
    await photo_file.download_to_drive(temp_path)
    
    # Вычисляем хеш присланного фото
    user_hash = get_image_hash(temp_path)
    
    # Ищем совпадение
    found = None
    for category, hashes in REF_HASHES.items():
        if user_hash in hashes:
            found = category
            break
    
    if found:
        await update.message.reply_text(f'Похоже на нарушение: {found}')
    else:
        await update.message.reply_text('Не удалось распознать нарушение. Попробуй другое фото.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == '__main__':
    main()
