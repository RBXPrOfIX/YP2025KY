```markdown
# AI Music Assistant 🎵

**Клиент-серверное приложение для поиска схожих музыкальных треков по текстам песен**  
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 📖 Описание
Проект представляет собой интеллектуальную систему для анализа текстов песен и поиска семантически схожих треков. Реализованы:
- **Сервер** на FastAPI с REST API.
- **Клиент** с графическим интерфейсом (PyQt5).
- Интеграция с внешними API (Genius, Lyrics.ovh).
- Механизмы шифрования данных и многопоточная обработка.

## 🌟 Особенности
- **Сбор текстов песен** из открытых источников.
- **Семантический анализ** текстов с использованием NLP (spaCy, Gensim).
- **Поиск схожих треков** на основе косинусной схожести векторов.
- **Шифрование данных** при передаче (AES-256 + HMAC).
- **Логирование** операций в SQLite.
- Поддержка **многопоточности** (≥10 одновременных запросов).

---

## 🛠 Технологии
- **Сервер**: FastAPI, SQLAlchemy, Uvicorn
- **Клиент**: PyQt5, Requests
- **Анализ данных**: spaCy, Gensim, Scikit-learn
- **База данных**: SQLite (+ Redis для кэширования)
- **Тестирование**: Locust, Pytest
- **Деплой**: Docker, Docker Compose

---

## ⚙️ Установка
1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/RBXPrOfIX/YP2025KY.git
   cd YP2025KY
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Настройте окружение:
   - Создайте файл `.env`:
     ```ini
     DATABASE_URL=sqlite:///./database.db
     SECRET_KEY=your_secret_key
     ```

---

## 🚀 Запуск проекта
**Сервер:**
```bash
python server.py
```
- Доступен на `http://localhost:8000`
- Документация API: `http://localhost:8000/docs`

**Клиент:**
```bash
python client.py
```

**Docker:**
```bash
docker-compose up --build
```

---

## 📡 API Endpoints
| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `GET` | `/get_lyrics` | Получить текст песни |
| `GET` | `/find_similar` | Найти схожие треки |
| `GET` | `/generate_report` | Сгенерировать отчет (CSV/JSON) |

**Пример запроса:**
```http
GET http://localhost:8000/get_lyrics?track_name=Bohemian%20Rhapsody&artist=Queen
```

---

## 🖥 Графический интерфейс
![GUI Demo](media/gui_demo.png)
- **Поля ввода**: Название трека, исполнитель.
- **Кнопки управления**: Запуск/остановка сервера.
- **Результаты**: Отображение текста песен и схожих треков.

---

## 🔒 Шифрование данных
- **Алгоритм**: AES-256 + HMAC
- **Ключи**: Хранятся в защищенном `.env`-файле.
- **Реализация**:
  ```python
  from cryptography.fernet import Fernet
  cipher = Fernet(os.getenv("SECRET_KEY"))
  encrypted_data = cipher.encrypt(data.encode())
  ```

---

## 📊 База данных
**Структура:**
- `lyrics`: Тексты песен, метаданные.
- `logs`: Логи запросов (IP, статус, устройство).
- `users`: Данные пользователей (зашифрованы).

**Миграции**: Alembic для управления схемой БД.

---

## 📈 Производительность
- **Нагрузочное тестирование** (Locust):  
  ![Locust Report](media/locust_stats.png)
- **Оптимизации**:
  - Пул соединений SQLAlchemy.
  - Индексы в БД.
  - Кэширование через Redis.

---

## 📂 Структура проекта
```
YP2025KY/
├── server.py            # Серверная часть
├── client.py           # Клиентское приложение
├── database.db         # База данных
├── requirements.txt    # Зависимости
├── Dockerfile          # Конфигурация Docker
└── docs/               # Документация
```

---

## 📄 Лицензия
[MIT License](LICENSE) © 2023 Катлюшкин С.Р., Янченко М.А.
```

[Скачать последнюю версию](https://github.com/RBXPrOfIX/YP2025KY/releases) | [Документация](docs/) | [Отчеты](reports/)
