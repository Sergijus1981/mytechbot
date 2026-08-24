import os
import hashlib
import urllib.request
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
print(f"Загружено категорий: {len(REF_HASHES)}")
for cat, hashes in REF_HASHES.items():
    print(f"{cat}: {len(hashes)} хешей")
TOKEN = os.getenv('TELEGRAM_TOKEN')

def download_file(url, dest_path):
    urllib.request.urlretrieve(url, dest_path)

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
                    except:
                        continue
    return ref_hashes

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_HASHES = load_reference_hashes(os.path.join(BASE_DIR, '.'))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    temp_path = f"/tmp/{file.file_id}.jpg"
    await file.download_to_drive(temp_path)
    user_hash = get_md5(temp_path)
    
    for category, hashes in REF_HASHES.items():
        if user_hash in hashes:
            await update.message.reply_text(f'Найдено совпадение: {category}')
            return
    
    await update.message.reply_text('Не найдено совпадений.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == '__main__':
    main()
