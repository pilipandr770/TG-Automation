# How to Run the Application

## Quick Start

### Option 1: Run Everything (Flask + Telethon)
```bash
python run.py
```

This starts:
- **Flask Web Server** on http://localhost:5000 (Admin Panel)
- **Telethon Background Worker** (Telegram client, discovery, publishing, etc.)

### Option 2: Run Only Web Server (for development)
```bash
python run.py --web-only
```

Use this if you're developing the web interface and don't need Telegram functionality.

### Option 3: Run Only Background Worker
```bash
python run.py --worker-only
```

Use this if the web server is running elsewhere and you only need the Telegram client.

### Option 4: Check Configuration
```bash
python run.py --check
```

Verifies:
- Python packages installed ✓
- Database initialized ✓
- Environment variables configured ✓

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│         Telegram Automation Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐          ┌──────────────────────┐     │
│  │  Flask Web App   │          │ Telethon Background  │     │
│  │  (Admin Panel)   │◄────────►│   Worker             │     │
│  │  :5000           │          │                      │     │
│  │                  │          │  - Discovery Module  │     │
│  │  - Settings      │          │  - Audience Scanner  │     │
│  │  - Instructions  │  Redis   │  - Publisher Module  │     │
│  │  - Post Manager  │  pub/sub │  - Invitation Module │     │
│  │  - Logs          │          │  - Conversation AI   │     │
│  └──────────────────┘          └──────────────────────┘     │
│           │                              │                   │
│           └──────────────────────────────┘                   │
│                     (shared database)                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## What Each Part Does

### Flask Web Application (:5000)
- Admin panel for managingbusiness goals
- Settings configuration
- AI instructions editor
- Content source management
- Post publishing interface
- Conversation history viewer
- Telegram session management

### Telethon Background Worker
Runs continuously in the background and handles:

1. **Discovery Module** - Finds relevant Telegram channels
2. **Audience Scanner** - Analyzes channel members
3. **Publisher Module** - Publishes content to channels (with scheduling)
4. **Invitation Module** - Sends invitations to users
5. **Conversation Handler** - AI responses to DMs and channel comments
6. **Rate Limiter** - Prevents flooding with built-in delays

---

## How Modules Communicate

```
Admin Panel                    Background Worker
    │                                   │
    ├─ Save settings ────────────────┤
    │   (Redis pub/sub)               │
    │                                   ├─ Run discovery
    │                                   ├─ Scan audience
    │                                   ├─ Publish content
    │                                   ├─ Send invitations
    └─ Read activity logs ◄──────────┤
       (Database queries)              │
                                       └─ Update database
```

**No interference** because:
- ✓ Flask writes to database, Telethon reads
- ✓ Telethon writes to database, Flask reads
- ✓ Redis pub/sub for on-demand commands
- ✓ Built-in delays prevent flooding
- ✓ SQLite locks handle concurrent access automatically

---

## Module Delays (Built-in)

Each module has automatic delays to prevent interfering with each other:

| Module | Default Delay | Configurable |
|--------|---------------|--------------|
| Discovery Cycle | 60-120 minutes | Via `AppConfig` |
| Audience Scan | 24-48 hours | Via `AppConfig` |
| Publisher Cycle | 60 minutes | Via `AppConfig` |
| Invitation Batch | Per-senddelay | Rate limiter |
| Conversation Handler | Per-message | (real-time) |

These delays are configured in `AppConfig` table and managed automatically.

---

## Environment Variables Needed

```bash
# Required for Flask
FLASK_ENV=development          # or 'production'
SECRET_KEY=your-secret-key     # Session encryption

# Required for Telegram (optional for web-only mode)
TELEGRAM_API_ID=...            # Get from https://my.telegram.org/
TELEGRAM_API_HASH=...          # Get from https://my.telegram.org/
TELEGRAM_PHONE=+1234567890     # Your Telegram account phone

# Required for OpenAI
OPENAI_API_KEY=...             # From https://platform.openai.com/

# Optional (for production)
DATABASE_URL=...               # PostgreSQL on Render
REDIS_URL=...                  # Redis on Render
```

---

## Troubleshooting

### "Port 5000 already in use"
```bash
# Kill the process using port 5000
lsof -i :5000                  # Find process ID
kill -9 <PID>                  # Kill it
```

### "Telegram credentials issue"
- The app works fine without Telegram credentials
- Flask will start normally
- Telethon worker will wait for credentials
- Use admin panel to set up Telegram session

### "Database locked"
- SQLite automatically handles this
- If you see errors, restart the app
- Consider upgrading to PostgreSQL for production

### "Modules not communicating"
- Check Redis connection (if using `--worker-only`)
- Verify database file exists and is writable
- Check logs for specific error messages

---

## For Production (Render.com)

Use `render.yaml` which defines separate services:

```yaml
services:
  - type: web
    startCommand: "gunicorn --timeout 120 wsgi:app"
    
  - type: background_worker
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python telethon_runner.py"
```

Each runs independently with proper resource allocation.

---

## Quick Start Examples

```bash
# Local development
python run.py --web-only
# Then open http://localhost:5000/admin

# Full local testing (with Telegram)
export TELEGRAM_API_ID=123456
export TELEGRAM_API_HASH=abcdef123456
python run.py

# Production (via render.yaml)
# Automatically handles both services
```

---

## Key Points

✓ **Single command**: `python run.py` starts everything
✓ **No interference**: Built-in delays and SQLite locks prevent conflicts
✓ **Coordinated**: Flask and Telethon share one database
✓ **Scalable**: Easily runs on Render as separate processes
✓ **Reliable**: Graceful shutdown with signal handling
✓ **Monitored**: Real-time logs show what each module is doing
