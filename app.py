import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from PIL import Image
import tempfile
import hashlib

TOKEN = os.getenv('TELEGRAM_TOKEN')

def get_phash(image_path):
    """Простой перцептивный хеш через Pillow"""
    img = Image.open(image_path).convert('L').resize((8, 8))
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return int(bits, 2)

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
                        h = get_phash(full_path)
                        ref_hashes[category].append(h)
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
    
    try:
        user_hash = get_phash(temp_path)
    except:
        await update.message.reply_text('Не удалось обработать фото.')
        return
    
    # Ищем похожее (чем меньше разница, тем лучше)
    found = None
    best_diff = 100
    for category, hashes in REF_HASHES.items():
        for h in hashes:
            diff = abs(user_hash - h)  # простейшее сравнение
            if diff < best_diff:
                best_diff = diff
                found = category
    
    # Порог чувствительности: 40 бит (можно подкрутить)
    if found and best_diff < 40:
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
