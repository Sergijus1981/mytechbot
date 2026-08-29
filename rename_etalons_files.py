import os

etalon_dir = r"C:\Users\ЗС\mytechbot\etalons"

# Проходим по всем папкам внутри etalons
for root, dirs, files in os.walk(etalon_dir):
    for fname in files:
        full_path = os.path.join(root, fname)
        category = os.path.basename(root)  # имя папки (birki_etalon, ...)
        ext = os.path.splitext(fname)[1]
        
        # Определяем номер для нового имени
        existing = [f for f in os.listdir(etalon_dir) if f.startswith(category) and f.endswith(ext)]
        num = len(existing) + 1
        new_name = f"{category}_{num}{ext}"
        new_path = os.path.join(etalon_dir, new_name)
        
        os.rename(full_path, new_path)
        print(f"✅ {fname} → {new_name}")

# Удаляем пустые папки
for root, dirs, files in os.walk(etalon_dir, topdown=False):
    for d in dirs:
        try:
            os.rmdir(os.path.join(root, d))
            print(f"🗑️ Удалена папка: {d}")
        except OSError:
            pass

print("🎉 Все файлы переименованы и перемещены!")