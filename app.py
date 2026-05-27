import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8917838537:AAHm8tzHuNRbX5_CaRNKxqQl9o_Nj-p7U1E"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Бот работает, но распознавание фото временно отключено. Скоро починим.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я тебя слышу, но фото пока не обрабатываю.")
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Твой токен (читается из переменной окружения)
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Создаём приложение
app = Application.builder().token(TOKEN).build()
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    print("✅ Бот запущен (упрощённая версия)")
    app.run_polling()

if __name__ == "__main__":
    main()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ Бот запущен и слушает сообщения...")
    app.run_polling()

if __name__ == "__main__":
    main(Commit changes)
