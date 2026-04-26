# Telegram AI Bot

Локальная Python-версия n8n workflow `Ai_assistant_for_me`.

Бот умеет:

- отвечать в Telegram на текстовые сообщения;
- принимать голосовые сообщения и распознавать их через OpenAI;
- держать память последних сообщений по каждому чату;
- принимать заявки с именем и номером телефона;
- сохранять заявки локально в SQLite;
- опционально дублировать заявки в Google Sheets.

## Важно по безопасности

В присланном JSON был виден Telegram bot token. Его нужно перевыпустить в BotFather:

1. Откройте `@BotFather`.
2. Выберите бота.
3. Нажмите `API Token` / `Revoke current token`.
4. Новый токен вставьте в `.env`.

## Запуск в PyCharm

Откройте папку `telegram_ai_bot` как отдельный проект в PyCharm, затем в терминале:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

Если раньше этот же бот работал в n8n, выключите workflow в n8n. При запуске Python-бот автоматически удаляет старый Telegram webhook, потому что локальный режим использует polling.

После `copy .env.example .env` откройте `.env` и вставьте реальные ключи:

```env
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
```

## Голосовые сообщения

Telegram отправляет voice-сообщения в формате OGG/OPUS. Для стабильной работы бот конвертирует их через FFmpeg в MP3 перед отправкой в OpenAI.

Установите FFmpeg и добавьте его в `PATH`. Проверка:

```powershell
ffmpeg -version
```

Если FFmpeg не установлен, текстовые сообщения будут работать, а голосовые бот попросит настроить.

## Google Sheets

По умолчанию Google Sheets выключен, чтобы бот работал без дополнительных платформ.

Чтобы включить:

1. Создайте service account в Google Cloud.
2. Скачайте JSON ключ и положите его в `telegram_ai_bot/service_account.json`.
3. Дайте email service account доступ к вашей Google таблице.
4. В `.env` включите:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_CREDENTIALS_FILE=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=...
GOOGLE_SHEETS_WORKSHEET=Лист1
```

Колонки в таблице: `Имя`, `Номер`, `telegram_id`.

## Команды

- `/start` - приветствие.
- `/reset` - очистить память диалога и черновик заявки для текущего чата.
- `/sync_sheets` - повторно отправить в Google Sheets заявки, которые сохранились локально, но ещё не попали в таблицу.
- `/check_sheets` - показать, к какой таблице подключён бот и какие последние строки он видит.

## Где хранятся данные

- Диалоги и заявки: `data/bot.sqlite3`
- Временные аудиофайлы удаляются автоматически после обработки.

OpenAI API всё равно оплачивается по тарифам OpenAI, но n8n или другая платная платформа для работы бота больше не нужна.

## Если заявка не появилась в Google Sheets

Бот всегда сохраняет заявку локально в SQLite. Если Google Sheets был недоступен, можно повторить отправку:

```powershell
python sync_sheets.py
```

Или отправить боту команду:

```text
/sync_sheets
```

Проверить, куда именно бот пишет строки:

```powershell
python check_sheets.py
```
