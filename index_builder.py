def get_embedding(image_path):
    try:
        # Проверяем, что файл существует и читается
        from PIL import Image
        img = Image.open(image_path)
        img.verify()  # проверяем целостность
        img = Image.open(image_path)  # открываем заново после verify
        
        # Пробуем получить эмбеддинг через predict с embed=True
        results = model.predict(source=image_path, embed=True, verbose=False)
        
        # Если results — это список, и у первого элемента есть embeds
        if results and hasattr(results[0], 'embeds') and results[0].embeds is not None:
            emb = results[0].embeds[0].cpu().numpy()
            return emb
        else:
            # Альтернативный способ: извлечь эмбеддинг через forward без головы
            # Для этого нужно получить доступ к модели PyTorch
            import torch
            from ultralytics.nn.tasks import ClassificationModel
            
            # Если модель ещё не инициализирована как PyTorch модель, делаем это
            if not hasattr(model, 'model'):
                raise Exception("Модель не имеет атрибута .model")
            
            # Препроцессинг изображения
            from torchvision import transforms
            transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            img_tensor = transform(img).unsqueeze(0)  # добавляем batch
            
            # Отключаем голову классификации (последний слой)
            # Для YOLOv8-cls: модель.model - это PyTorch Sequential, последний слой - Linear
            # Убираем последний слой
            model.eval()
            with torch.no_grad():
                features = model.model[:-1](img_tensor)  # все слои кроме последнего
                # Если features - это тензор, преобразуем в numpy
                if isinstance(features, torch.Tensor):
                    emb = features.flatten().cpu().numpy()
                    return emb
                else:
                    # Если модель вернула что-то другое
                    return None
    except Exception as e:
        print(f"Ошибка при обработке {image_path}: {e}")
        return None
