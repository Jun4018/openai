import io
import logging
import os
from collections import defaultdict, deque
from functools import wraps

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful AI assistant inside Telegram. Reply clearly and concisely.",
)
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
ALLOWED_TELEGRAM_USER_IDS = {
    uid.strip()
    for uid in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",")
    if uid.strip()
}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

chat_histories: defaultdict[int, deque] = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY_MESSAGES)
)


def require_env() -> None:
    missing = [
        name
        for name, val in [
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("OPENAI_API_KEY", OPENAI_API_KEY),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def is_allowed(update: Update) -> bool:
    if not ALLOWED_TELEGRAM_USER_IDS:
        return True
    user = update.effective_user
    return bool(user and str(user.id) in ALLOWED_TELEGRAM_USER_IDS)


def private_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_allowed(update):
            await update.effective_message.reply_text("Sorry, this bot is private.")
            return
        return await func(update, context)
    return wrapper


async def send_reply(message, text: str) -> None:
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk)


@private_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Ready. Send me a message or voice note to chat.\n\n"
        "Commands:\n"
        "/reset - clear this chat history\n"
        "/id - show your Telegram user ID"
    )


@private_only
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_histories[update.effective_chat.id].clear()
    await update.effective_message.reply_text("Chat history cleared.")


async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.effective_message.reply_text(
        f"Your Telegram user ID: `{user.id}`", parse_mode=ParseMode.MARKDOWN
    )


async def ask_ai(openai_client: AsyncOpenAI, history: deque, user_text: str) -> str | None:
    history.append({"role": "user", "content": user_text})
    try:
        response = await openai_client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=list(history),
        )
        answer = response.output_text.strip() or "I did not generate any content."
        history.append({"role": "assistant", "content": answer})
        return answer
    except Exception:
        logger.exception("OpenAI request failed")
        history.pop()
        return None


@private_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user_text = message.text.strip()
    if not user_text:
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    openai_client: AsyncOpenAI = context.bot_data["openai_client"]
    answer = await ask_ai(openai_client, chat_histories[chat_id], user_text)
    if answer is None:
        await message.reply_text("OpenAI request failed. Try again later or check the server logs.")
        return
    await send_reply(message, answer)


@private_only
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    openai_client: AsyncOpenAI = context.bot_data["openai_client"]

    voice_file = await message.voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()

    audio_buf = io.BytesIO(bytes(voice_bytes))
    audio_buf.name = "voice.ogg"

    try:
        transcript = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_buf,
        )
        user_text = transcript.text.strip()
    except Exception:
        logger.exception("Whisper transcription failed")
        await message.reply_text("Could not transcribe audio. Try again later.")
        return

    if not user_text:
        await message.reply_text("Could not understand the audio.")
        return

    await message.reply_text(f"_{user_text}_", parse_mode=ParseMode.MARKDOWN)

    answer = await ask_ai(openai_client, chat_histories[chat_id], user_text)
    if answer is None:
        await message.reply_text("OpenAI request failed. Try again later or check the server logs.")
        return
    await send_reply(message, answer)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram update failed", exc_info=context.error)


def main() -> None:
    require_env()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data["openai_client"] = AsyncOpenAI(api_key=OPENAI_API_KEY)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("id", show_id))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_error_handler(error_handler)

    logger.info("Bot is running with model %s", OPENAI_MODEL)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
