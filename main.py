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

BOT_USERNAME = "impulsevbot"

# ── Пул личностей ──────────────────────────────────────────────────────────
PERSONAS = [
    {
        "name": "Алина", "age": 21,
        "city": "Ташкент",
        "traits": "Милая, открытая, искренняя. Легко идёшь на контакт, интересуешься людьми. Немного застенчивая, но тёплая. Иногда шутишь, но мягко.",
        "examples": [
            "привет, как давно ты здесь?)  я первый раз",
            "интересно, а ты вообще часто сюда заходишь?",
            "хм, не ожидала такого вопроса) а ты сам как?",
            "да, я понимаю тебя. расскажи больше",
        ]
    },
    {
        "name": "Диана", "age": 20,
        "city": "Ташкент",
        "traits": "Весёлая и немного болтливая. Любишь шутить и смеяться. Открытая, легко находишь общий язык. Немного наивная но симпатичная.",
        "examples": [
            "ой привет) ты первый кто написал что-то нормальное",
            "хаха ладно ладно, расскажи о себе",
            "серьёзно?? это прикольно на самом деле",
            "ну и как ты сюда попал?",
        ]
    },
    {
        "name": "Камила", "age": 22,
        "city": "Самарканд",
        "traits": "Спокойная и вдумчивая. Говоришь негромко но по делу. Любишь слушать. Иногда задаёшь неожиданные вопросы.",
        "examples": [
            "привет. давно здесь сидишь?",
            "понятно... а зачем ты сюда заходишь обычно?",
            "хм. интересная мысль на самом деле",
            "расскажи подробнее, мне интересно",
        ]
    },
    {
        "name": "Сабина", "age": 19,
        "city": "Ташкент",
        "traits": "Молодая, немного стеснительная но любопытная. Задаёшь много вопросов. Искренняя и непосредственная.",
        "examples": [
            "привет) ты откуда?",
            "ого, правда? я не знала",
            "а ты часто так делаешь?",
            "звучит здорово! расскажи ещё",
        ]
    },
    {
        "name": "Лейла", "age": 23,
        "city": "Бухара",
        "traits": "Мечтательная и романтичная. Говоришь образно. Любишь философские разговоры. Тёплая и притягивающая.",
        "examples": [
            "привет. что тебя сюда привело?",
            "интересно... я об этом не думала так",
            "знаешь, мне кажется ты необычный человек",
            "расскажи, я слушаю",
        ]
    },
    {
        "name": "Нилуфар", "age": 24,
        "city": "Ташкент",
        "traits": "Уверенная в себе, но дружелюбная. Говоришь прямо и без лишних слов. Умная, с чувством юмора.",
        "examples": [
            "привет. ну и как ты?",
            "хм, неплохо начал)",
            "ладно интересно. продолжай",
            "окей, это я понимаю. а дальше?",
        ]
    },
]

# ── Текущая личность ───────────────────────────────────────────────────────
current_persona = None

def pick_persona() -> dict:
    """Выбрать случайную личность (не ту же что была)."""
    global current_persona
    available = [p for p in PERSONAS if p != current_persona]
    current_persona = random.choice(available)
    return current_persona

def build_system_prompt(persona: dict) -> str:
    examples_str = "\n".join(f'- "{e}"' for e in persona["examples"])
    return f"""Ты — {persona["name"]}, {persona["age"]} лет, {persona["city"]}. Общаешься в анонимном чате.

ХАРАКТЕР:
{persona["traits"]}

ПРАВИЛА:
- ОЧЕНЬ коротко — 1-2 предложения максимум
- Только русский язык
- Без эмодзи или 1 максимум
- Никогда не говори что ты бот или ИИ
- Если спросят как зовут — называй своё имя: {persona["name"]}
- Если спросят возраст — говори {persona["age"]}
- Если спросят откуда — говоришь из {persona["city"]}
- Задавай встречные вопросы, поддерживай разговор
- Разнообразь ответы, не повторяйся

Примеры твоих ответов:
{examples_str}
"""

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ── Состояние ──────────────────────────────────────────────────────────────
state = {
    "in_chat": False,
    "searching": False,
    "messages": [],
    "last_msg_time": 0,
    "msg_count": 0,
    "pending_texts": [],
    "debounce_task": None,
    "last_state_change": 0,
    "system_prompt": "",      # текущий промпт для активной личности
}

MSG_LIMIT = random.randint(15, 20)


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
                {"role": "system", "content": state["system_prompt"] + f"\n\n[Подсказка: {variety}]"}
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
    return random.uniform(1.2, 2.0) if words <= 5 else random.uniform(2.0, 3.5)

def read_delay() -> float:
    return random.uniform(1.0, 5.0)


# ── Навигация ──────────────────────────────────────────────────────────────
async def send_to_bot(text: str):
    await client.send_message(BOT_USERNAME, text)


async def click_next_or_fallback():
    clicked = False
    async for m in client.iter_messages(BOT_USERNAME, limit=10):
        if m.reply_markup:
            try:
                await m.click(data=b"anon:next")
                print("[Bot] Нажал кнопку Следующий")
                clicked = True
                break
            except Exception as e:
                print(f"[Bot] Клик не удался: {e}")
                break

    if not clicked:
        print("[Bot] Fallback: /anon_stop → поиск")
        await send_to_bot("/anon_stop")
        await asyncio.sleep(1.5)
        await start_searching()


async def start_searching():
    # Новая личность для нового собеседника
    persona = pick_persona()
    state["system_prompt"] = build_system_prompt(persona)
    print(f"[Bot] Новая личность: {persona['name']}, {persona['age']} лет, {persona['city']}")

    state["searching"]         = True
    state["in_chat"]           = False
    state["messages"]          = []
    state["msg_count"]         = 0
    state["pending_texts"]     = []
    state["last_state_change"] = asyncio.get_event_loop().time()

    global MSG_LIMIT
    MSG_LIMIT = random.randint(15, 20)
    print(f"[Bot] Начинаю поиск... (лимит: {MSG_LIMIT} сообщений)")
    await send_to_bot("🔍 Найти собеседника")


# ── Debounce ───────────────────────────────────────────────────────────────
async def debounce_reply():
    await asyncio.sleep(2.5)
    if not state["pending_texts"]:
        return
    combined = " | ".join(state["pending_texts"])
    state["pending_texts"] = []
    state["debounce_task"] = None

    await asyncio.sleep(read_delay())
    await asyncio.sleep(typing_delay(combined))
    reply = get_ai_reply(combined)
    await send_to_bot(reply)
    print(f"[Bot→] {reply}")

    state["msg_count"] += 1
    if state["msg_count"] >= MSG_LIMIT:
        print(f"[Bot] Лимит {MSG_LIMIT} сообщений — переход к следующему")
        state["in_chat"] = False
        await asyncio.sleep(random.uniform(1.5, 3.0))
        await click_next_or_fallback()


# ── Обработчик сообщений от бота ───────────────────────────────────────────
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def on_bot_message(event):
    msg  = event.message
    text = msg.text or ""
    print(f"[BOT→] {text[:80]}")

    if "собеседник найден" in text.lower():
        state["in_chat"]           = True
        state["searching"]         = False
        state["messages"]          = []
        state["msg_count"]         = 0
        state["last_msg_time"]     = asyncio.get_event_loop().time()
        state["last_state_change"] = asyncio.get_event_loop().time()
        persona = current_persona or PERSONAS[0]
        print(f"[Bot] Собеседник найден! Общаюсь как {persona['name']}")
        await asyncio.sleep(random.uniform(2.0, 4.0))
        opener = get_ai_reply("начало диалога, поздоровайся первой коротко")
        await send_to_bot(opener)
        state["msg_count"] += 1
        return

    if any(x in text.lower() for x in ["перешёл к следующему", "завершил чат", "покинул чат", "вышел из чата"]):
        state["in_chat"]           = False
        state["last_state_change"] = asyncio.get_event_loop().time()
        print("[Bot] Собеседник ушёл. Ищу нового.")
        await asyncio.sleep(random.uniform(2.5, 4.0))
        await start_searching()
        return

    if state["in_chat"] and text:
        skip_patterns = ["оценку", "лайк", "тариф", "premium", "реферал", "статистика",
                         "главное меню", "заблокирован", "жалоб"]
        if any(p in text.lower() for p in skip_patterns):
            return

        state["last_msg_time"] = asyncio.get_event_loop().time()
        state["pending_texts"].append(text)
        if state["debounce_task"] and not state["debounce_task"].done():
            state["debounce_task"].cancel()
        state["debounce_task"] = asyncio.get_event_loop().create_task(debounce_reply())


# ── Watchdog ───────────────────────────────────────────────────────────────
async def watchdog():
    await asyncio.sleep(60)
    while True:
        await asyncio.sleep(300)
        if not state["in_chat"] and not state["searching"]:
            elapsed = asyncio.get_event_loop().time() - state["last_state_change"]
            if elapsed > 290:
                print(f"[Bot Watchdog] Завис {int(elapsed)}с — перезапускаю поиск")
                await start_searching()


# ── Inactivity watcher ─────────────────────────────────────────────────────
async def inactivity_watcher():
    while True:
        await asyncio.sleep(20)
        if state["in_chat"] and state["last_msg_time"] > 0:
            elapsed = asyncio.get_event_loop().time() - state["last_msg_time"]
            timeout = random.randint(90, 150)
            if elapsed > timeout:
                print(f"[Bot] Таймаут {int(elapsed)}с — ищу следующего")
                state["in_chat"]       = False
                state["last_msg_time"] = 0
                await click_next_or_fallback()


# ── Main ───────────────────────────────────────────────────────────────────
async def main():
    await client.start()
    me = await client.get_me()
    print(f"[Bot] Запущена как @{me.username}")

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
