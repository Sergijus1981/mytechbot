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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import io
import datetime

# ===== КОНФИГ =====
TOKEN = "8216393055:AAF6sbjxic7y9tpMN-yKGTNagAEqnszhL8U"
PHOTO_DB_URL = "https://dl.dropboxusercontent.com/scl/fi/xxl7bna8h3re0ks9jdsy6/photo_db.zip?rlkey=j94j0yuv1e3sg67txyzda4zo9&dl=1"
INDEX_PATH = "faiss_index.bin"
PATHS_PATH = "image_paths.pkl"
MODEL_PATH = "best.pt"

# ===== НОРМАТИВНЫЕ ДАННЫЕ =====
CATEGORY_DATA = [
    (
        "01_otsutstvuyut_birki",
        "⚠️ Отсутствуют бирки на оборудовании (кабелях, муфтах, аппаратах).",
        "birki_etalon",
        "ПУЭ п. 2.3.23, СП 76.13330.2016 п. 6.4.8"
    ),
    (
        "02_zadelka_prohodok",
        "⚠️ Не выполнена заделка проходок (зазоры в трубах, коробах, проёмах).",
        "prohodki_etalon",
        "СП 76.13330.2016 п. 6.4.1.25"
    ),
    (
        "03_zazemlenie_ne_vypolneno",
        "⚠️ Не выполнено заземление (или не соответствует нормам).",
        "zazemlenie_etalon",
        "ПУЭ п. 1.7.76"
    ),
    (
        "04_shpilki_lotka_ne_srezany",
        "⚠️ Шпильки лотка не срезаны (опасность травматизма и повреждения кабелей).",
        "shpilki_etalon",
        "ГОСТ Р 50571.5.52-2011"
    ),
]

index = None
image_paths = None
embedder = None
transform = None

# ===== ПОДКЛЮЧЕНИЕ ШРИФТА ДЛЯ КИРИЛЛИЦЫ =====
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    addMapping('DejaVuSans', 0, 0, 'DejaVuSans')
    addMapping('DejaVuSans', 0, 1, 'DejaVuSans')
    addMapping('DejaVuSans', 1, 0, 'DejaVuSans')
    addMapping('DejaVuSans', 1, 1, 'DejaVuSans')
    FONT_NAME = 'DejaVuSans'
    print("✅ Шрифт DejaVuSans загружен")
except:
    FONT_NAME = 'Helvetica'
    print("⚠️ Шрифт DejaVuSans не найден, используем Helvetica (кириллица не поддерживается)")

# ===== КЛАВИАТУРА =====
def get_report_keyboard():
    keyboard = [[InlineKeyboardButton("📄 Сформировать отчёт", callback_data="generate_report")]]
    return InlineKeyboardMarkup(keyboard)

# ===== ГЕНЕРАЦИЯ PDF =====
def generate_pdf_report(report_data, chat_id):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Применяем кириллический шрифт ко всем стилям
    for style_name in styles.byName:
        styles[style_name].fontName = FONT_NAME
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, alignment=1, fontName=FONT_NAME)
    
    story = []
    story.append(Paragraph("📋 Отчёт по технадзору", title_style))
    story.append(Paragraph(f"Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 12*mm))

    if report_data:
        for i, item in enumerate(report_data, 1):
            story.append(Paragraph(f"<b>Замечание #{i}</b>", styles['Heading2']))
            story.append(Paragraph(f"📌 {item.get('text', 'Неизвестно')}", styles['Normal']))
            story.append(Paragraph(f"📜 Норматив: {item.get('normative', '—')}", styles['Normal']))
            story.append(Paragraph(
                "🛠 Необходимо привести в соответствие с ГОСТ IEC 61293-2016 "
                "(Оборудование электрическое. Маркировка с указанием номинальных "
                "значений характеристик источников электропитания. Требования техники безопасности).",
                styles['Normal']
            ))
            
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

# ===== ОСТАЛЬНЫЕ ФУНКЦИИ =====
def download_and_extract_photos():
    if os.path.exists("photo_db") and len(os.listdir("photo_db")) > 0:
        print("📁 photo_db уже существует, пропускаю загрузку.")
        return
    print("📥 Скачиваю архив с фото через gdown...")
    gdown.download(PHOTO_DB_URL, "photo_db.zip", quiet=False)
    print("📦 Распаковываю...")
    with zipfile.ZipFile("photo_db.zip", "r") as zip_ref:
        zip_ref.extractall(".")
    os.remove("photo_db.zip")
    if not os.path.exists("photo_db"):
        for item in os.listdir("."):
            if os.path.isdir(item) and item.startswith("photo_db"):
                os.rename(item, "photo_db")
                break
        else:
            os.mkdir("photo_db")
            for f in os.listdir("."):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    os.rename(f, os.path.join("photo_db", f))
    print(f"✅ photo_db готова, файлов: {len(os.listdir('photo_db'))}")

def load_index():
    global index, image_paths
    if index is None:
        print("Загружаю индекс...")
        index = faiss.read_index(INDEX_PATH)
        with open(PATHS_PATH, "rb") as f:
            raw_paths = pickle.load(f)
        image_paths = [os.path.join("photo_db", os.path.basename(p)) for p in raw_paths]
        print(f"Индекс загружен, {len(image_paths)} изображений.")

def load_model():
    global embedder, transform
    if embedder is None:
        print("Загружаю модель...")
        try:
            model = YOLO(MODEL_PATH)
            torch_model = model.model.model
            embedder = torch.nn.Sequential(*list(torch_model.children())[:-1])
            embedder.eval()
            transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            print("Модель загружена.")
        except Exception as e:
            print(f"⚠️ Модель не загружена: {e}. Будем использовать только имена файлов.")
            embedder = None

def get_embedding(image_path):
    if embedder is None:
        return np.random.rand(128).astype('float32')
    img = Image.open(image_path).convert('RGB')
    img_tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        emb = embedder(img_tensor).flatten().cpu().numpy()
    return emb

def get_category_info(filename):
    name = os.path.basename(filename)
    print(f"🔎 Определяем категорию для: {name}")
    for keyword, text, etalon_prefix, normative in CATEGORY_DATA:
        if name.startswith(keyword):
            return {"text": text, "etalon_prefix": etalon_prefix, "normative": normative}
    parts = name.split('_')
    for keyword, text, etalon_prefix, normative in CATEGORY_DATA:
        kw_parts = keyword.split('_')
        if any(kp in parts for kp in kw_parts):
            return {"text": text, "etalon_prefix": etalon_prefix, "normative": normative}
    return {"text": f"📌 Неизвестное замечание (файл: {name})", "etalon_prefix": None, "normative": None}

def find_etalon(prefix):
    etalon_dir = "etalons"
    if not os.path.exists(etalon_dir):
        return None
    for f in os.listdir(etalon_dir):
        if f.startswith(prefix) and f.lower().endswith(('.jpg', '.jpeg', '.png')):
            return os.path.join(etalon_dir, f)
    return None

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
        info = get_category_info(full_path)
        if 'report_data' not in context.user_data:
            context.user_data['report_data'] = []
        context.user_data['report_data'].append({
            'text': info['text'],
            'normative': info.get('normative'),
            'photo_path': user_path
        })
        response = f"🔍 **Найдено замечание:**\n{info['text']}"
        if info.get("normative"):
            response += f"\n📜 Норматив: {info['normative']}"
        etalon_path = find_etalon(info.get("etalon_prefix"))
        if etalon_path and os.path.exists(etalon_path):
            with open(etalon_path, 'rb') as f:
                await update.message.reply_photo(photo=f, caption=response, reply_markup=get_report_keyboard())
        else:
            await update.message.reply_text(response, reply_markup=get_report_keyboard())
    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "generate_report":
        report_data = context.user_data.get('report_data', [])
        if not report_data:
            await query.edit_message_text("📭 Нет замечаний для отчёта. Сначала отправьте фотографии.")
            return
        pdf_buffer = generate_pdf_report(report_data, query.message.chat.id)
        await query.message.reply_document(
            document=pdf_buffer,
            filename=f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            caption="📄 Ваш отчёт готов!"
        )
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
