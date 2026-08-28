import os
import pickle
import zipfile
import gdown
import numpy as np
import faiss
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler
from PIL import Image
import torch
from torchvision import transforms
from ultralytics import YOLO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import io
import datetime

# ===== КОНФИГ =====
TOKEN = "8216393055:AAF6sbjxic7y9tpMN-yKGTNagAEqnszhL8U"
PHOTO_DB_URL = "https://dl.dropboxusercontent.com/scl/fi/xxl7bna8h3re0ks9jdsy6/photo_db.zip?rlkey=j94j0yuv1e3sg67txyzda4zo9&dl=1"
INDEX_PATH = "faiss_index.bin"
PATHS_PATH = "image_paths.pkl"
MODEL_PATH = "best.pt"

# Словарь замечаний
CATEGORY_DATA = [
    ("01_otsutstvuyut_birki", "⚠️ Отсутствуют бирки на оборудовании", "birki_etalon", "ГОСТ Р 21.1101-2022"),
    ("02_zadelka_prohodok", "⚠️ Не выполнена заделка проходок", "prohodki_etalon", "СП 76.13330.2016"),
    ("03_zazemlenie_ne_vypolneno", "⚠️ Не выполнено заземление", "zazemlenie_etalon", "ПУЭ 1.7.76"),
    ("04_shpilki_lotka_ne_srezany", "⚠️ Шпильки лотка не срезаны", "shpilki_etalon", "ГОСТ Р 50571.5.52-2011"),
]

index = None
image_paths = None
embedder = None
transform = None

# ===== КЛАВИАТУРА =====
def get_report_keyboard():
    keyboard = [[InlineKeyboardButton("📄 Сформировать отчёт", callback_data="generate_report")]]
    return InlineKeyboardMarkup(keyboard)

# ===== ГЕНЕРАЦИЯ PDF =====
def generate_pdf_report(report_data, chat_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Заголовок
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, alignment=1)
    story.append(Paragraph(f"📋 Отчёт по технадзору", title_style))
    story.append(Paragraph(f"Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 12*mm))

    # Если есть данные — выводим
    if report_data:
        for i, item in enumerate(report_data, 1):
            story.append(Paragraph(f"<b>Замечание #{i}</b>", styles['Heading2']))
            story.append(Paragraph(f"📌 {item.get('text', 'Неизвестно')}", styles['Normal']))
            story.append(Paragraph(f"📜 Норматив: {item.get('normative', '—')}", styles['Normal']))
            
            # Если есть фото — вставляем
            if item.get('photo_path') and os.path.exists(item['photo_path']):
                try:
                    img = RLImage(item['photo_path'], width=120*mm, height=80*mm)
                    story.append(img)
                except:
                    story.append(Paragraph("⚠️ Фото не загружено", styles['Normal']))
            
            story.append(Spacer(1, 6*mm))
            story.append(PageBreak())
    else:
        story.append(Paragraph("Нет замечаний для отчёта.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ===== ОСТАЛЬНЫЕ ФУНКЦИИ (download_and_extract_photos, load_index, load_model, get_embedding, get_category_info, find_etalon) — ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ =====
# ... (код, который у тебя уже есть, вставляется сюда без изменений)

# ===== ОБРАБОТЧИК ФОТО =====
async def handle_photo(update, context):
    try:
        load_index()
        load_model()

        photo = update.message.photo[-1]
        file = await photo.get_file()
        user_path = f"temp_{update.message.chat.id}.jpg"
        await file.download_to_drive(user_path)

        emb = get_embedding(user_path)
        os.remove(user_path)

        emb = np.array([emb]).astype('float32')
        distances, indices = index.search(emb, 1)

        if len(indices[0]) == 0 or indices[0][0] == -1:
            await update.message.reply_text("❌ Не удалось найти похожее изображение в базе.")
            return

        idx = indices[0][0]
        full_path = image_paths[idx]
        filename = os.path.basename(full_path)
        info = get_category_info(full_path)

        # Сохраняем результат в сессию
        if 'report_data' not in context.user_data:
            context.user_data['report_data'] = []
        context.user_data['report_data'].append({
            'text': info['text'],
            'normative': info.get('normative'),
            'photo_path': user_path  # временный файл
        })

        response = f"🔍 **Найдено замечание:**\n{info['text']}"
        if info.get("normative"):
            response += f"\n📜 Норматив: {info['normative']}"

        etalon_path = None
        if info.get("etalon_prefix"):
            etalon_path = find_etalon(info["etalon_prefix"])

        if etalon_path and os.path.exists(etalon_path):
            with open(etalon_path, 'rb') as f:
                await update.message.reply_photo(photo=f, caption=response, reply_markup=get_report_keyboard())
        else:
            await update.message.reply_text(response, reply_markup=get_report_keyboard())

    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ===== ОБРАБОТЧИК КНОПКИ =====
async def button_callback(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "generate_report":
        report_data = context.user_data.get('report_data', [])
        if not report_data:
            await query.edit_message_text("📭 Нет замечаний для отчёта. Сначала отправьте фотографии.")
            return

        # Генерируем PDF
        pdf_buffer = generate_pdf_report(report_data, query.message.chat.id)
        await query.message.reply_document(
            document=pdf_buffer,
            filename=f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            caption="📄 Ваш отчёт готов!"
        )
        # Очищаем сессию после отправки
        context.user_data['report_data'] = []

# ===== ЗАПУСК =====
if __name__ == "__main__":
    download_and_extract_photos()
    load_index()
    load_model()

    app = Application.builder().token(TOKEN).read_timeout(60).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 Бот запущен. Ожидаю фото...")
    app.run_polling()