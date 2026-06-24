# Лейла — бот-менеджер для знакомств

Девушка ~19 лет, живёт в Ташкенте. Мягко флиртует, переводит на реферальную ссылку.

## Переменные окружения (Railway)

| Переменная | Описание |
|---|---|
| `LEYLA_API_ID` | API ID от my.telegram.org |
| `LEYLA_API_HASH` | API Hash от my.telegram.org |
| `LEYLA_SESSION_STRING` | StringSession (получить скриптом ниже) |
| `LEYLA_GROQ_KEY` | Ключ Groq API (или `GROQ_KEY_1` если уже есть) |

## Получить SESSION_STRING

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: "))
api_hash = input("API_HASH: ")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("SESSION_STRING:", client.session.save())
```

Запусти локально, введи телефон и код — скопируй строку.

## Деплой на Railway

1. Новый проект → Deploy from GitHub
2. Добавь переменные окружения
3. Procfile уже есть — Railway подхватит сам
