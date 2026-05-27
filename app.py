import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.getenv('TELEGRAM_TOKEN')

# Создаём приложение (именно так, без лишних пробелов в начале строк)
app = Application.builder().token(TOKEN).build()

async def start(update, context):
    await update.message.reply_text('Привет! Я бот технадзора. Отправь фото.')

async def handle_photo(update, context):
    # Здесь будет твоя логика распознавания нарушений
    await update.message.reply_text('Фото получено, ищу нарушение...')

app.add_handler(CommandHandler('start', start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == '__main__':
    app.run_polling()
