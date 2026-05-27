import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
import imagehash
from PIL import Image
import tempfile

TOKEN = os.getenv('TELEGRAM_TOKEN')

def load_reference_hashes(photos_dir='.'):
    ref_hashes = {}
    if not os.path.exists(photos_dir):
        return ref_hashes
    for category in os.listdir(photos_dir):
        cat_path = os.path.join(photos_dir, category)
        if os.path.isdir(cat_path) and not category.startswith('.'):
            ref_hashes[category] = []
            for fname in os.listdir(cat_path):
                if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    full_path = os.path.join(cat_path, fname)
                    try:
                        img = Image.open(full_path)
                        hash_val = imagehash.phash(img)
                        ref_hashes[category].append(hash_val)
                    except:
                        continue
    return ref_hashes

REF_HASHES = load_reference_hashes('.')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Скачиваем фото
    photo_file = await update.message.photo[-1].get_file()
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = f.name
    await photo_file.download_to_drive(temp_path)
    
    # Вычисляем phash присланного фото
    try:
        user_img = Image.open(temp_path)
        user_hash = imagehash.phash(user_img)
    except:
        await update.message.reply_text('Не удалось обработать фото.')
        return
    
    # Ищем похожее (допускаем отличие до 5 бит)
    found = None
    min_diff = 10
    for category, hashes in REF_HASHES.items():
        for h in hashes:
            diff = user_hash - h
            if diff < min_diff:
                min_diff = diff
                found = category
    
    if found and min_diff < 5:
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
