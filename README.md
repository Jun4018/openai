# Telegram AI Bot

A simple Telegram AI bot. Send it a Telegram message and it replies through the OpenAI API.

## Run Locally

1. Open `@BotFather` in Telegram, create a bot, and copy the `TELEGRAM_BOT_TOKEN`.
2. Copy the sample environment file:

```powershell
Copy-Item .env.example .env
```

3. Edit `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

4. Install dependencies and start the bot:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

## Private Mode

Start the bot, then send this command in Telegram:

```text
/id
```

Put the returned user ID in `.env`:

```env
ALLOWED_TELEGRAM_USER_IDS=123456789
```

Restart the bot. Only the listed Telegram user IDs can use it.

## Run While Your Computer Is Off

If you run the bot locally, it stops when your computer shuts down. To keep it available while your computer is off, deploy it to a cloud host such as Render, Railway, Fly.io, a VPS, or any always-on server.

### Render Blueprint

This repo includes `render.yaml`. Render reads this file from the root of your Git repository and creates a background worker service.

1. Push this folder to a GitHub repository.
2. Open Render and create a new Blueprint from that repository.
3. Render will ask for the secret values marked with `sync: false`.
4. Fill in:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `ALLOWED_TELEGRAM_USER_IDS`

Leave `ALLOWED_TELEGRAM_USER_IDS` blank if you do not want private mode.

Cloud start command:

```bash
python bot.py
```

Set these environment variables on the cloud platform:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SYSTEM_PROMPT`
- `ALLOWED_TELEGRAM_USER_IDS`

The default model is `gpt-5.4-mini`, a good speed/cost choice for a Telegram bot. You can use `gpt-5.5` for stronger reasoning.

## Commands

- `/start`: start using the bot
- `/reset`: clear the current chat memory
- `/id`: show your Telegram user ID
