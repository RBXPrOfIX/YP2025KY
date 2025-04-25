# 1. Базовый образ
FROM python:3.11-slim

# 2. Окружение Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Рабочая папка внутри контейнера
WORKDIR /app

# 4. Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 5. Копируем весь код приложения
COPY . .

# 6. Экспонируем порт (тот же, что у uvicorn)
EXPOSE 8000

# 7. Точка входа
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

