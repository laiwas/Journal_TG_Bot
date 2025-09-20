# Journal Telegram Bot

Телеграм-бот для ведения ежедневного дневника с распознаванием речи и структурированием записей через LLM.  
Поддерживает интеграцию с **Notion** для сохранения итогов.

## ✨ Возможности
- 🎙️ Приём голосовых сообщений → расшифровка (Whisper/faster-whisper).
- 📝 Анализ текста и раскладка по секциям:
  - Дела и мысли (подробный список)
  - Чувства (кратко)
  - Три победы за день
  - История дня (StoryWorthy, развёрнуто)
  - Оценка СДВГ (0–100)
  - Action Points (чекбоксы: Книга, Записи, RPG, Финансы)
- 📤 Сохранение в Notion (In Development).
- 📊 Команды:
  - `/newday` — начать новый день
  - `/summary` — показать сводку за сегодня

## 🚀 Локальный запуск

1. Клонировать репозиторий:
   bash
   git clone https://github.com/you/journal-tg-bot.git
   cd journal-tg-bot

2. Создать виртуальное окружение и установить зависимости: 
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt


3. Создать файл .env и добавить туда:
    TELEGRAM_BOT_TOKEN=ваш_токен_бота
    OPENAI_API_KEY=ваш_openai_api_key

# Если используете Notion:
NOTION_TOKEN=secret_xxx
NOTION_DB_ID=xxxxxxxxxxxxxxxxxxxx

4. Запустить бота:
    python bot.py

🐳 Деплой через Docker (Railway / VPS)
    Собрать контейнер:
    docker build -t journal-bot .


    Запустить:
    docker run -d --restart=always --env-file .env journal-bot

📦 requirements.txt

Минимальный набор зависимостей:
aiogram==3.13.1
python-dotenv==1.0.1
requests==2.32.3
ffmpeg-python==0.2.0
faster-whisper==1.0.3
openai==1.*

📌 Примечания

Для работы распознавания требуется ffmpeg (ставится автоматически в Dockerfile).
Модель whisper по умолчанию tiny (быстро и дёшево). Можно переключить в stt.py.
Если используете Railway — не забудьте Clear Cache после изменения requirements.txt.