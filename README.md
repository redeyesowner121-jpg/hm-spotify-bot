# 🤖 H&M + Spotify Telegram Automation Bot

A personal Telegram bot that automates H&M account creation, Spotify code retrieval from H&M profile, and Spotify code redemption — using only your own authorized accounts via official website interfaces.

> **⚠️ Compliance**: This bot uses only official website interfaces via browser automation. It **never** bypasses CAPTCHA, anti-bot protections, or any security mechanisms. All operations pause for manual completion when security challenges appear.

---

## Features

| Feature | Description |
|---------|-------------|
| 🛒 **Create H&M Account** | Automates registration on H&M website (India/UK region) |
| 🎵 **Create Spotify Account** | Creates Spotify account with same email (name from email prefix) |
| 🎶 **Get Spotify Code** | Retrieves Spotify voucher/redeem code from H&M profile |
| 🎁 **Redeem Spotify Code** | Redeems code on Spotify's official redeem page |
| 👤 **Account Status** | View registered accounts and session status |
| 🔐 **Session Management** | View and manage active browser sessions |
| ❌ **Logout / Clear Session** | Securely wipe all stored data |

## Security

- ✅ Credentials encrypted with Fernet (AES-128-CBC)
- ✅ Passwords deleted from Telegram chat immediately
- ✅ Single authorized user (Telegram ID whitelist)
- ✅ Session cookies encrypted in database
- ✅ No hardcoded credentials — everything from `.env`
- ✅ CAPTCHA detected but **never bypassed**
- ✅ No credential harvesting, mass-creation, or third-party automation

---

## Prerequisites

- **Python 3.11+**
- **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- **Your Telegram User ID** (get from [@userinfobot](https://t.me/userinfobot))

---

## Installation

### 1. Clone and setup

```bash
git clone <your-repo-url>
cd hm-spotify-bot
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Install Playwright browsers

```bash
playwright install chromium
```

### 3. Configure environment

```bash
# Copy the template
cp .env.example .env
```

Edit `.env` with your values:

```env
# Get from @BotFather
TELEGRAM_BOT_TOKEN=123456:ABCdefGHIjklMNOpqrsTUVwxyz

# Your Telegram user ID
AUTHORIZED_USER_IDS=6898461453

# Generate encryption key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-generated-fernet-key

# Browser mode
BROWSER_HEADLESS=true

# H&M base URL
HM_BASE_URL=https://www2.hm.com
```

### 4. Generate encryption key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output to `ENCRYPTION_KEY` in your `.env` file.

### 5. Run the bot

```bash
python bot.py
```

---

## Docker Deployment

### Build and run

```bash
docker-compose up -d --build
```

### View logs

```bash
docker-compose logs -f bot
```

### Stop

```bash
docker-compose down
```

---

## Railway Deployment (Pro Plan)

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo>
git push -u origin main
```

### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app)
2. Create a new project → Deploy from GitHub repo
3. Add environment variables in the Railway dashboard:
   - `TELEGRAM_BOT_TOKEN`
   - `AUTHORIZED_USER_IDS=6898461453`
   - `ENCRYPTION_KEY` (generated key)
   - `BROWSER_HEADLESS=true`
   - `HM_BASE_URL=https://www2.hm.com`
   - `DATABASE_PATH=data/bot.db`
4. Railway will auto-detect the `Dockerfile` and deploy

### 3. Railway configuration

The `railway.toml` file is pre-configured with:
- Dockerfile builder
- 2 CPUs, 512MB RAM (Pro plan)
- Auto-restart on failure

---

## Usage

1. Open your bot in Telegram
2. Send `/start`
3. Use the inline buttons:

```
🛒 Create H&M Account    → Region → Email → Password → Confirm
🎵 Create Spotify Account → Email → Password → Confirm
🎶 Get Spotify Code       → Region → (Login if needed) → Retrieve
🎁 Redeem Spotify Code    → (Login if needed) → Confirm → Redeem
👤 Account Status         → View all accounts & sessions
🔐 Session Management     → View session details
❌ Logout / Clear Session  → Confirm → Wipe everything
```

### CAPTCHA Handling

When a CAPTCHA or security challenge appears:
1. Bot **pauses automatically** and notifies you
2. You complete the challenge manually (bot provides instructions)
3. Bot resumes after the challenge is resolved
4. If not resolved within 5 minutes, the operation times out

---

## Project Structure

```
hm-spotify-bot/
├── bot.py                  # Main entry point
├── config.py               # Environment configuration
├── database.py             # Async SQLite with encrypted fields
├── security.py             # Fernet encryption + auth guard
├── browser.py              # Playwright browser manager
├── hm_client.py            # H&M website automation
├── spotify_client.py       # Spotify website automation
├── handlers/
│   ├── __init__.py
│   ├── common.py           # Shared utilities, keyboards, constants
│   ├── start.py            # /start command + main menu
│   ├── hm_handlers.py      # H&M account creation flow
│   ├── spotify_handlers.py # Spotify create/get-code/redeem flows
│   └── session_handlers.py # Account status, sessions, logout
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container image
├── docker-compose.yml      # Docker Compose
├── railway.toml            # Railway deployment config
└── README.md               # This file
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ENCRYPTION_KEY is required` | Generate key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `TELEGRAM_BOT_TOKEN is required` | Get token from [@BotFather](https://t.me/BotFather) |
| Bot doesn't respond | Check that your Telegram user ID matches `AUTHORIZED_USER_IDS` |
| Browser crash on Railway | Ensure `BROWSER_HEADLESS=true` and sufficient memory (512MB+) |
| Selectors not working | H&M/Spotify may have updated their website. Check logs and update selectors in `hm_client.py`/`spotify_client.py` |
| CAPTCHA timeout | Increase timeout in `browser.py` `wait_for_captcha_resolution()` |
| Session expired | Use Logout then re-login |

---

## Important Notes

- This bot is for **personal use only** with your own authorized accounts
- No third-party accounts, credentials, or data are ever accessed
- Website selectors may need updates if H&M/Spotify change their HTML
- Always comply with the Terms of Service of H&M and Spotify
- The bot operates within official website interfaces only

---

## License

For personal use only. Not for distribution or commercial use.
