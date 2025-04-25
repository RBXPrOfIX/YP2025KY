# Lyrics Insight 🎵

**Интеллектуальная система анализа текстов песен и поиска семантически схожих треков**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green)](https://fastapi.tiangolo.com/)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-orange)](https://riverbankcomputing.com/software/pyqt/)

---

## 📖 Краткое описание
Система включает:

- **`server/`**: FastAPI сервис с REST API, NLP- и ML-компонентами для обработки и хранения лирики.
- **`client/`**: PyQt5 приложение для интерактивного поиска, отображения текста и похожих треков.
- **`populate_random.py`**: скрипт для массовой загрузки треков через Genius и Last.fm и заполнения БД.

Все компоненты могут запускаться локально или в Docker-контейнерах.

---

## 🌟 Ключевые возможности

1. **Сбор текстов песен** через API Genius и Last.fm, с фильтрацией дубликатов и версий.
2. **Шифрование** запросов и ответов AES-GCM (AES-256) с Base64.
3. **Семантический анализ** (intfloat/multilingual-e5-large) и **эмоциональная оценка** (cardiffnlp/twitter-xlm-roberta).
4. **Экстракция тем** по словарю в `themes.json` и векторному порогу.
5. **Поиск похожих** треков по косинусной схожести эмбеддингов и SBERT.
6. **Многопоточность**: QThread в клиенте, ThreadPoolExecutor в скрипте populate.
7. **Логирование**: файлы `server.log`, `populate_random.log`, `client.log`; таблица `logs` в SQLite.
8. **Миграции**: на данный момент ручные ALTER TABLE через `init_db()`.
9. **Docker Compose** для быстрого развёртывания.

---

## 🛠 Стек технологий

| Компонент     | Библиотеки и инструменты                             |
|---------------|------------------------------------------------------|
| **Сервер**    | FastAPI, Uvicorn, SQLAlchemy, lyricsgenius, backoff  |
| **Клиент**    | PyQt5, Requests, cryptography                         |
| **NLP/ML**    | Transformers, Sentence-Transformers, SciPy, NLTK      |
| **Шифрование**| Cryptography (AESGCM)                                 |
| **База данных**| SQLite                                               |
| **Развёртывание**| Docker, Docker Compose                             |

---

## 📥 Предварительные шаги

1. Установите **Python 3.9+** и **Git**.
2. (Опционально) Установите **Docker Desktop**.
3. Скопируйте этот репозиторий:
   ```powershell
   git clone https://github.com/ВАШ_ПРОФИЛЬ/lyrics-insight.git
   cd lyrics-insight
   ```

---

## ⚙️ Локальная установка

### 1. Виртуальная среда и зависимости

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.env.txt     # зависимости для скриптов и сборки
```  

### 2. Конфигурация `.env`

Создайте файл `.env` в корне проекта со следующими переменными:

```dotenv
# Ключ шифрования AES-GCM (Base64)
ENC_KEY_B64=<32-байтный_ключ_Base64>

# Путь к БД
DATABASE_URL=sqlite:///./server/database.db

# API токены
GENIUS_TOKEN=<ваш_Genius_API_token>
LASTFM_API_KEY=<ваш_LastFM_API_key>
```

#### Получение токенов
- [Genius API](https://genius.com/api-clients)
- [Last.fm API](https://www.last.fm/api/account/create)

---

### 3. Сборка Docker-контейнеров (опционально)

```powershell
docker-compose build
```  
- Сервис `api` (FastAPI) собирается из `server/Dockerfile`.
- БД монтируется: `./server/database.db:/app/database.db`.

---

## 🚀 Запуск приложения

### A. В Docker

```powershell
docker-compose up -d      # запуск в фоне
docker-compose logs -f    # логи сервиса
docker-compose down       # остановка и очистка
```  
API доступно по `http://localhost:8000`.

### B. Локально (без Docker)

#### Сервер
```powershell
cd server
pip install -r ../requirements_server.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```  
- Swagger UI: `http://localhost:8000/docs`

#### Клиент
```powershell
cd client
pip install -r requirements.txt
python main.py
```  
- Появится окно QApplication с полями **Трек** и **Исполнитель**.

---

## 🔄 Наполнение базы: `populate_random.py`

Скрипт выбирает случайные треки по списку терминов, фильтрует по Last.fm и PUSH-ит в `/get_lyrics`:

```powershell
# из корня проекта
.\.venv\Scripts\Activate.ps1
pip install -r requirements.env.txt   # чтобы были requests, backoff, tqdm
python populate_random.py
```  
**Параметры** через `.env`:
- `MAX_REQUESTS` — макс. запросов к Genius (по умолчанию 1500)
- `WORKERS` — число потоков (по умолчанию 8)
- `REQUEST_TIMEOUT`, `GENIUS_TIMEOUT`

Лог в `populate_random.log`.

---

## 📡 API Эндпоинты

### `/get_lyrics` (POST)
- **Вход**: JSON `{ "data": "<encrypted_payload>" }`
- **Декодирование**: AESGCM URL-safe base64 → JSON `track_name`, `artist`
- **Выход**: `{ data: "<encrypted_response>" }`, где в раскрытом виде:
  ```json
  {
    "track": "...",
    "artist": "...",
    "lyrics": "...",
    "genre": ["pop", "rock", ...],
    "emotion": 0.1234
  }
  ```

### `/find_similar` (POST)
- **Вход**: `{ data: encrypted(token) }` (тот же формат с `track_name` и `artist`)
- **Выход**: список из 5 похожих треков в поле `similar_tracks`:
  ```json
  {
    "similar_tracks": [
      { "track": "...", "artist": "...", "similarity": 95.2, ... },
      ...
    ]
  }
  ```

---

## 🖥 Клиентское приложение

![GUI Demo](media/gui_demo.png)

1. **Поиск**: ввод названия трека и исполнителя → кнопка **Найти текст**.
2. **Прогресс**: индикатор загрузки запросов.
3. **Список**: дерево похожих треков с цветовой индикацией сходства.
4. **Детали**: двойной клик по элементу открывает всплывающее окно с полным текстом и жанрами.

---

## 🔒 Безопасность и шифрование

- **Алгоритм**: AES-GCM (12‑байтовый IV, 16‑байтовый тег).
- **Ключ**: 32 байта, URL-safe Base64 (`ENC_KEY_B64`).
- **Реализация**:
  ```python
  from cryptography.hazmat.primitives.ciphers.aead import AESGCM
  aes = AESGCM(KEY)
  ct = aes.encrypt(iv, payload_bytes, None)
  ```

---

## 📂 Структура проекта

```
lyrics-insight/
├── .env                     # переменные окружения и ключи
├── docker-compose.yml       # конфигурация для Docker Compose
├── populate_random.py       # скрипт наполнения БД случайными треками
├── requirements.env.txt     # общие зависимости проекта
├── client/                  # клиентское приложение на PyQt5
│   ├── main.py              # точка входа для GUI
│   ├── requirements.txt     # зависимости клиента
│   └── lyrics_insight/      # модуль клиента
│       ├── __init__.py
│       ├── api_worker.py    # QThread для API-запросов
│       ├── config.py        # конфигурация клиента (URL, логи)
│       ├── crypto.py        # шифрование AES-GCM на клиенте
│       ├── main_window.py   # UI и логика приложения
│       ├── popup.py         # окно детального просмотра лирики
│       └── titlebar.py      # кастомный заголовок окна
└── server/                  # FastAPI сервис и вспомогательные модули
    ├── schemas.py           # Pydantic схемы запросов/ответов
    ├── requirements_server.txt # зависимости серверной части
    ├── models.py            # ORM-модели SQLAlchemy
    ├── main.py              # инициализация и запуск FastAPI
    ├── Dockerfile           # образ сервера
    ├── database.py          # init_db и сессии базы данных
    ├── database.db          # файл SQLite (при наличии локально)
    ├── config.py            # конфигурация логирования и констант
    ├── __init__.py          # пакет Python
    ├── .dockerignore        # исключения для Docker
    ├── services/            # бизнес-логика и ML/NLP-анализ
    │   ├── themes.py
    │   ├── themes.json
    │   ├── semantic.py
    │   ├── lyrics.py
    │   ├── lastfm.py
    │   ├── emotion.py
    │   └── crypto.py
    ├── gui/                 # панель администрирования (если применимо)
    │   └── control_panel.py
    └── api/                 # маршруты REST API
        └── endpoints.py
```

---

*Создано с любовью к музыке и к чистому коду!*

