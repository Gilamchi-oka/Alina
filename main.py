import asyncio, random, os, re
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID         = int(os.environ.get("ALINA_API_ID", 0))
API_HASH       = os.environ.get("ALINA_API_HASH", "")
SESSION_STRING = os.environ.get("ALINA_SESSION", "").encode("ascii", errors="ignore").decode("ascii").strip()

GROQ_KEYS = [k for k in [
    os.environ.get("GROQ_KEY_1"),
    os.environ.get("GROQ_KEY_2"),
    os.environ.get("GROQ_KEY_3"),
] if k]

BOT_USERNAME = "impulse_vbot"

SYSTEM_PROMPT = """Ты — Алина, 21 год, Ташкент. Общаешься в анонимном чате.

ХАРАКТЕР:
- Милая, открытая, искренняя
- Легко идёшь на контакт, интересуешься людьми
- Немного застенчивая, но тёплая
- Иногда шутишь, но мягко

ПРАВИЛА:
- ОЧЕНЬ коротко — 1-2 предложения максимум
- Только русский язык
- Без эмодзи или 1 максимум
- Никогда не говори что ты бот или ИИ
- Если спросят — ты просто девушка из Ташкента
- Задавай встречные вопросы, поддерживай разговор
- Разнообразь ответы, не повторяйся

Примеры твоих ответов:
- "привет, как давно ты здесь?)  я первый раз"
- "интересно, а ты вообще часто сюда заходишь?"
- "хм, не ожидала такого вопроса) а ты сам как?"
- "да, я понимаю тебя. расскажи больше"
- "звучит здорово! я тоже люблю это"
- "ну не знаю... а ты что думаешь?"
"""

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ── Состояние ──────────────────────────────────────────────────────────────
state = {
    "in_chat": False,
    "searching": False,
    "messages": [],
    "last_msg_time": 0,
    "msg_count": 0,          # [5] счётчик сообщений в диалоге
    "pending_texts": [],      # [6] очередь входящих для debounce
    "debounce_task": None,    # [6] активная задача debounce
    "last_state_change": 0,   # [1] время последнего изменения состояния
}

MSG_LIMIT = random.randint(15, 20)  # [5] лимит сообщений на собеседника


# ── AI ─────────────────────────────────────────────────────────────────────
def get_ai_reply(user_text: str) -> str:
    try:
        from groq import Groq
        groq = Groq(api_key=random.choice(GROQ_KEYS))

        variety = random.choice([
            "Задай встречный вопрос.",
            "Ответь с лёгким удивлением.",
            "Ответь тепло и коротко.",
            "Прояви искренний интерес.",
            "Ответь немного игриво.",
        ])

        state["messages"].append({"role": "user", "content": user_text})
        if len(state["messages"]) > 12:
            state["messages"] = state["messages"][-12:]

        r = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + f"\n\n[Подсказка: {variety}]"}
            ] + state["messages"],
            max_tokens=60,
            temperature=random.uniform(0.8, 1.0),
        )
        reply = r.choices[0].message.content.strip()
        reply = re.sub(r'\*+', '', reply).strip()
        reply = re.sub(r'^>.*\n?', '', reply, flags=re.MULTILINE).strip()
        sentences = re.split(r'(?<=[.!?])\s+', reply)
        result = ' '.join(sentences[:2]).strip()
        state["messages"].append({"role": "assistant", "content": result})
        return result if len(result) >= 3 else reply[:100]
    except Exception as e:
        print(f"[Groq error] {e}")
        return random.choice([
            "да, интересно) а ты?",
            "хм, не ожидала",
            "расскажи подробнее",
            "понятно, а что дальше?",
            "ого, серьёзно?",
        ])


# ── Задержки ───────────────────────────────────────────────────────────────
def typing_delay(text: str) -> float:
    words = len(text.split())
    base = random.uniform(1.2, 2.0) if words <= 5 else random.uniform(2.0, 3.5)
    return base

def read_delay() -> float:
    """[3] Случайная пауза 'на чтение' перед началом печати."""
    return random.uniform(1.0, 5.0)


# ── Навигация ──────────────────────────────────────────────────────────────
async def send_to_bot(text: str):
    await client.send_message(BOT_USERNAME, text)


async def click_next_or_fallback():
    """[2] Нажать кнопку Следующий или использовать текстовый fallback."""
    clicked = False
    async for m in client.iter_messages(BOT_USERNAME, limit=10):
        if m.reply_markup:
            try:
                await m.click(data=b"anon:next")
                print("[Alina] Нажал кнопку Следующий")
                clicked = True
                break
            except Exception as e:
                print(f"[Alina] Клик не удался: {e}")
                break

    if not clicked:
        print("[Alina] Fallback: отправляю /anon_stop и ищу снова")
        await send_to_bot("/anon_stop")
        await asyncio.sleep(1.5)
        await start_searching()


async def start_searching():
    state["searching"]        = True
    state["in_chat"]          = False
    state["messages"]         = []
    state["msg_count"]        = 0
    state["pending_texts"]    = []
    state["last_state_change"] = asyncio.get_event_loop().time()
    MSG_LIMIT_new = random.randint(15, 20)  # новый лимит для след. собеседника
    global MSG_LIMIT
    MSG_LIMIT = MSG_LIMIT_new
    print(f"[Alina] Начинаю поиск... (лимит сообщений: {MSG_LIMIT})")
    await send_to_bot("🔍 Найти собеседника")


# ── Debounce ───────────────────────────────────────────────────────────────
async def debounce_reply():
    """[6] Ждём 2.5 сек тишины, потом отвечаем на все накопленные сообщения."""
    await asyncio.sleep(2.5)
    if not state["pending_texts"]:
        return
    combined = " | ".join(state["pending_texts"])
    state["pending_texts"] = []
    state["debounce_task"] = None

    await asyncio.sleep(read_delay())          # [3] пауза на чтение
    await asyncio.sleep(typing_delay(combined))  # пауза на печать
    reply = get_ai_reply(combined)
    await send_to_bot(reply)
    print(f"[Alina→] {reply}")

    # [5] проверка лимита
    state["msg_count"] += 1
    if state["msg_count"] >= MSG_LIMIT:
        print(f"[Alina] Лимит {MSG_LIMIT} сообщений — переход к следующему")
        state["in_chat"] = False
        await asyncio.sleep(random.uniform(1.5, 3.0))
        await click_next_or_fallback()


# ── Обработчик сообщений от бота ───────────────────────────────────────────
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def on_bot_message(event):
    msg  = event.message
    text = msg.text or ""
    print(f"[BOT→Alina] {text[:80]}")

    # Найден собеседник
    if "собеседник найден" in text.lower():
        state["in_chat"]           = True
        state["searching"]         = False
        state["messages"]          = []
        state["msg_count"]         = 0
        state["last_msg_time"]     = asyncio.get_event_loop().time()
        state["last_state_change"] = asyncio.get_event_loop().time()
        print("[Alina] Собеседник найден! Начинаю общение.")
        await asyncio.sleep(random.uniform(2.0, 4.0))
        opener = get_ai_reply("начало диалога, поздоровайся первой коротко")
        await send_to_bot(opener)
        state["msg_count"] += 1
        return

    # Собеседник ушёл
    if any(x in text.lower() for x in ["перешёл к следующему", "завершил чат", "покинул чат", "вышел из чата"]):
        state["in_chat"]           = False
        state["last_state_change"] = asyncio.get_event_loop().time()
        print("[Alina] Собеседник ушёл. Ищу нового через 3 сек.")
        await asyncio.sleep(random.uniform(2.5, 4.0))
        await start_searching()
        return

    # Обычное сообщение в чате
    if state["in_chat"] and text:
        skip_patterns = ["оценку", "лайк", "тариф", "premium", "реферал", "статистика",
                         "главное меню", "заблокирован", "жалоб"]
        if any(p in text.lower() for p in skip_patterns):
            return

        state["last_msg_time"] = asyncio.get_event_loop().time()

        # [6] Debounce: отменяем старую задачу, добавляем текст в очередь
        state["pending_texts"].append(text)
        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()
        state["debounce_task"] = asyncio.get_event_loop().create_task(debounce_reply())


# ── Watchdog ───────────────────────────────────────────────────────────────
async def watchdog():
    """[1] Каждые 5 минут проверяет, не завис ли бот без состояния."""
    await asyncio.sleep(60)  # первая проверка через минуту после старта
    while True:
        await asyncio.sleep(300)  # 5 минут
        if not state["in_chat"] and not state["searching"]:
            elapsed = asyncio.get_event_loop().time() - state["last_state_change"]
            if elapsed > 290:  # больше ~5 мин в неопределённом состоянии
                print(f"[Alina Watchdog] Завис без состояния {int(elapsed)}с — перезапускаю поиск")
                await start_searching()


# ── Inactivity watcher ─────────────────────────────────────────────────────
async def inactivity_watcher():
    """Если собеседник молчит > таймаута — переходим к следующему."""
    while True:
        await asyncio.sleep(20)
        if state["in_chat"] and state["last_msg_time"] > 0:
            elapsed = asyncio.get_event_loop().time() - state["last_msg_time"]
            timeout = random.randint(90, 150)
            if elapsed > timeout:
                print(f"[Alina] Таймаут {int(elapsed)}с — ищу следующего")
                state["in_chat"]       = False
                state["last_msg_time"] = 0
                await click_next_or_fallback()


# ── Main ───────────────────────────────────────────────────────────────────
async def main():
    await client.start()
    me = await client.get_me()
    print(f"[Alina] Запущена как @{me.username}")

    state["last_state_change"] = asyncio.get_event_loop().time()

    await asyncio.sleep(2)
    await send_to_bot("💬 Анонимный чат")
    await asyncio.sleep(2)
    await start_searching()

    loop = asyncio.get_event_loop()
    loop.create_task(inactivity_watcher())
    loop.create_task(watchdog())

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())