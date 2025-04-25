# Lyrics Insight 🎵

**Интеллектуальная система анализа текстов песен и поиска семантически схожих треков**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green)](https://fastapi.tiangolo.com/)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-orange)](https://riverbankcomputing.com/software/pyqt/)

---

## 📖 Описание
Lyrics Insight объединяет мощный сервер на FastAPI и клиент на PyQt5 для сбора, шифрования и семантического анализа текстов песен. Система автоматически получает тексты через API Genius и Last.fm, вычисляет эмбеддинги, глубокую эмоциональную оценку и темы, а затем находит похожие по смыслу треки.

---

## 🌟 Ключевые особенности

- **Сбор текста песен**: интеграция с Genius и Last.fm API
- **Шифрование передачи**: AES-GCM (по стандарту AES-256) для защиты данных
- **Семантический и эмоциональный анализ**: трансформеры от Hugging Face и собственная модель DeepEmotion
- **Метрики сходства**: косинусная схожесть эмбеддингов и SBERT
- **Экстракция тем**: лексико-стеммовая и векторно-основанная обработка
- **Многопоточность**: асинхронные запросы и пул воркеров для высокой производительности
- **Логирование**: SQLite для хранения логов запросов и истории
- **Развёртывание в Docker**: единое управление через `docker-compose`

---

## 🛠 Технологический стек

| Компонент      | Технологии                                 |
|----------------|--------------------------------------------|
| **Сервер**     | FastAPI, Uvicorn, SQLAlchemy, Alembic       |
| **Клиент**     | PyQt5, Requests, QThread                    |
| **NLP & ML**   | Transformers, Sentence-Transformers, SciPy   |
| **Шифрование** | Cryptography (AESGCM)                       |
| **БД**         | SQLite                                      |
| **Тестирование** | PyTest, Locust                             |
| **Деплой**     | Docker, Docker Compose                      |

---

## ⚙️ Установка и подготовка окружения

1. **Клонирование репозитория**
   ```powershell
   git clone https://github.com/ВАШ_ПРОФИЛЬ/lyrics-insight.git
   cd lyrics-insight
   ```
2. **Создание виртуальной среды и установка зависимостей**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.env.txt
   ```
3. **Генерация ключа шифрования**
   ```powershell
   $bytes = New-Object Byte[] 32
   (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
   [Convert]::ToBase64String($bytes)
   ```
   Добавьте результат в файл `.env`:
   ```dotenv
   ENC_KEY_B64=<ваш_KEY>
   DATABASE_URL=sqlite:///./database.db
   GENIUS_TOKEN=<ваш_Genius_API_token>
   LASTFM_API_KEY=<ваш_LastFM_API_key>
   ```
4. **Получение API токенов**
   - [Genius API](https://genius.com/api-clients)
   - [Last.fm API](https://www.last.fm/api/account/create)

---

## 🚀 Запуск

### С Docker

```powershell
docker-compose build
docker-compose up -d
``` 
Сервис будет доступен на `http://localhost:8000`.

```powershell
docker-compose logs -f   # Просмотр логов
docker-compose down      # Остановить и удалить контейнеры
```

### Локальный запуск

**Сервер** (без Docker):
```powershell
cd server
pip install -r ../requirements_server.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Клиент**:
```powershell
cd client
pip install -r requirements.txt
python main.py
```

---

## 📡 API Эндпоинты

| Метод | URL           | Описание                             |
|-------|---------------|--------------------------------------|
| POST  | `/get_lyrics` | Получить лирику и метаданные трека   |
| POST  | `/find_similar` | Найти 5 семантически похожих треков |

**Пример запроса** (шифрованный payload):
```json
POST http://localhost:8000/get_lyrics
{
  "data": "<encrypted_token>"
}
```

---

## 🖥 Клиентское приложение

![GUI Demo](media/gui_demo.png)

1. Запустите `python main.py` из папки `client`.
2. Введите **Название трека** и **Исполнителя**, нажмите **Найти текст**.
3. Просмотрите текст песни и список схожих треков.
4. Двойной клик по треку откроет детальный просмотр в отдельном окне.

---

## 🔒 Безопасность и шифрование

- **Алгоритм**: AES-GCM (AES-256)
- **Реализация**:
  ```python
  from cryptography.hazmat.primitives.ciphers.aead import AESGCM
  aesgcm = AESGCM(key)
  encrypted = aesgcm.encrypt(iv, payload, None)
  ```
- Ключ хранится в `.env`, не коммитится в Git.

---

## 📂 Структура проекта

```
lyrics-insight/
├── .env
├── docker-compose.yml
├── populate_random.py
├── requirements.env.txt
├── server/
│   ├── main.py
│   ├── api/
│   ├── services/
│   ├── database.py
│   └── ...
├── client/
│   ├── main.py
│   ├── api_worker.py
│   ├── crypto.py
│   └── ...
└── media/                # скриншоты и демо GUI
```

---

*С любовью к музыке и коду!*

