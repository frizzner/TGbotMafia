# TGbotMafia

Telegram-бот для гри в мафію з кнопковим меню, ролями, фазами ночі/дня та голосуванням.

## Запуск локально

1. Встанови залежності:
   ```bash
   pip install -r requirements.txt
   ```
2. Запусти бота:
   ```bash
   python bot.py
   ```

## Для хостингу

- Додай токен бота в змінну середовища `TG_BOT_TOKEN` або в `config.py`.
- Для Render/Heroku/ Railway достатньо файлів `requirements.txt`, `runtime.txt` і `Procfile`.
