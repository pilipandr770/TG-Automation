# Telegram Automation Platform

Полностью автоматическое веб-приложение для работы в Telegram: поиск каналов, анализ целевой аудитории, рассылка приглашений, публикация контента и общение с подписчиками с монетизацией через Telegram Stars.

## Архитектура

**Dual-Process Model:**
- **Process 1:** Flask Web (Gunicorn) — Админ-панель
- **Process 2:** Telethon Worker — 24/7 Telegram соединение
- **Process 3:** RQ Worker — Пакетные задачи
- **Redis:** Очередь + rate limiting + pub/sub

## Tech Stack

- Flask 3.0, SQLAlchemy, Flask-Login
- Telethon (MTProto userbot)
- OpenAI API (gpt-4o-mini)
- Redis + RQ
- Bootstrap 5.3
- PostgreSQL (prod) / SQLite (dev)

## Quick Start (Local Development)

### 1. Установка зависимостей

```bash
cd telegram_automation
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///telegram_automation.db

# OpenAI
OPENAI_API_KEY=sk-your-key

# Telegram (get from https://my.telegram.org)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your-hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_TARGET_CHANNEL=@your_channel

# Redis (optional for local)
REDIS_URL=redis://localhost:6379/0
```

### 3. Создайте админа

```bash
flask create-admin
# Username: admin
# Email: admin@example.com
# Password: ********
```

### 4. Запустите Flask

```bash
flask run
```

Откройте http://localhost:5000 и войдите.

### 5. Настройте Telegram сессию

1. Перейдите в **Admin → Telegram Session**
2. Введите API ID, API Hash, Phone Number
3. Сохраните credentials

### 6. Запустите Telethon Worker (в отдельном терминале)

```bash
python telethon_runner.py
```

При первом запуске вам будет предложено ввести код подтверждения из Telegram.

## Modules

### Module 1: Channel Discovery (24/7)
- Автоматический поиск каналов/групп по ключевым словам
- Фильтры: min subscribers, comments, topic matching
- Автовступление в подходящие каналы

**Настройка:** Admin → Keywords

### Module 2: Target Audience
- Чтение сообщений в joined каналах
- AI-анализ пользователей (OpenAI + контекст)
- Сохранение контактов с confidence score

**Настройка:** Admin → Audience Criteria

### Module 3: Invitations
- 5-10 шаблонов сообщений (персонализация)
- Рандомные интервалы 1-3 мин
- СТРОГО 1 раз на контакт (UniqueConstraint)

**Настройка:** Admin → Templates

### Module 4: Content Publishing
- RSS / Reddit / Webpage парсинг
- AI rewriting (OpenAI)
- Автопубликация в канал

**Настройка:** Admin → Content Sources

### Module 5: Conversations & Payments
- AI-переписка с подписчиками (OpenAI)
- Telegram Stars платежи
- Автодоставка платного контента

**Настройка:** Admin → Paid Content

## Admin Panel (15 страниц)

1. **Dashboard** — статистика
2. **Keywords** — ключевые слова для поиска
3. **Channels** — найденные каналы
4. **Audience Criteria** — критерии ЦА
5. **Contacts** — целевые пользователи
6. **Templates** — шаблоны приглашений
7. **Invitation Log** — лог отправок
8. **Content Sources** — RSS/Reddit источники
9. **Published Posts** — опубликованные посты
10. **Paid Content** — платный контент
11. **Conversations** — диалоги
12. **Transactions** — платежи Stars
13. **OpenAI Settings** — промпты + бюджет
14. **Telegram Session** — статус сессии
15. **Settings** — общие настройки

## CLI Commands

```bash
# Create admin user
flask create-admin

# Run invitation batch (Module 3)
flask run-invitations --limit 10

# Run publisher (Module 4)
flask run-publisher --count 3

# Backup Telegram session
flask backup-session

# Daily stats snapshot
flask snapshot-stats
```

## Deploy на Render.com

1. **Push to GitHub**
2. **Create Render account**
3. **Import from GitHub** (выберите репозиторий)
4. **Render автоматически распознает `render.yaml`**
5. **Set Environment Variables** (в Render Dashboard):
   - `OPENAI_API_KEY`
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_PHONE`
   - `TELEGRAM_TARGET_CHANNEL`
6. **Deploy!**

Render создаст:
- Web service (Flask)
- Telethon worker (24/7)
- RQ worker
- Redis
- PostgreSQL
- 3 cron jobs

### После деплоя:

1. Откройте веб URL (из Render Dashboard)
2. Войдите как admin
3. Настройте Telegram Session
4. Telethon worker автоматически подключится (проверьте логи)

## Project Structure

```
telegram_automation/
├── app/
│   ├── __init__.py              # App factory + CLI
│   ├── models.py                # 16 моделей БД
│   ├── routes/
│   │   ├── admin_routes.py      # Admin CRUD
│   │   ├── auth_routes.py       # Login/logout
│   │   └── api_routes.py        # JSON API
│   ├── services/                # Бизнес-логика
│   │   ├── telegram_client.py   # Telethon wrapper
│   │   ├── openai_service.py    # OpenAI wrapper
│   │   ├── rate_limiter.py      # Rate limits
│   │   ├── discovery_service.py # Module 1
│   │   ├── audience_service.py  # Module 2
│   │   ├── invitation_service.py# Module 3
│   │   ├── publisher_service.py # Module 4
│   │   ├── conversation_service.py # Module 5
│   │   └── content_fetcher.py   # RSS/Reddit/Web
│   └── templates/admin/         # 17 Bootstrap шаблонов
├── telethon_runner.py           # Telethon worker entry
├── worker.py                    # RQ worker entry
├── wsgi.py                      # Gunicorn entry
├── config.py                    # Dev/Prod config
├── render.yaml                  # Render deployment
└── requirements.txt
```

## Database Models (16 таблиц)

- **User, AppConfig, TelegramSession** — Core
- **SearchKeyword, DiscoveredChannel** — Module 1
- **AudienceCriteria, Contact** — Module 2
- **InvitationTemplate, InvitationLog** — Module 3
- **ContentSource, PublishedPost** — Module 4
- **PaidContent, Conversation, ConversationMessage, StarTransaction** — Module 5
- **TaskLog, OpenAIUsageLog** — Logging

## Important Notes

### Rate Limiting (критично!)

Telegram агрессивно банит за автоматизацию. Дефолтные лимиты:
- Search: 2/min, 20/hour
- Join channel: 5/hour, 20/day
- Send message: 1/min, 20/hour

**Рекомендации:**
- Новый аккаунт (не личный!)
- Дайте аккаунту "созреть" 2-4 недели
- Начинайте с 2-3 приглашений в день
- Постепенно увеличивайте (10% в неделю)
- Рандомные интервалы

### Telethon Session Persistence

Render.com имеет ephemeral filesystem. Сессия сохраняется в PostgreSQL как `StringSession`. Hourly backup cron сохраняет сессию каждый час.

### OpenAI Costs

- **gpt-4o-mini:** $0.15/1M input, $0.60/1M output
- Предфильтр по keywords перед OpenAI (экономия)
- Daily budget cap в настройках

## Troubleshooting

### Telethon не подключается
- Проверьте логи: `Admin → Logs`
- Проверьте credentials: `Admin → Telegram Session`
- Telethon worker heartbeat: `API → /worker-status`

### OpenAI errors
- Проверьте API key в `.env`
- Проверьте daily budget: `Admin → OpenAI Settings`
- Логи usage: `Admin → Logs` → filter by `audience/publisher/conversation`

### Rate limits
- Проверьте Redis connection
- Уменьшите интервалы в `Admin → Settings`

## License

MIT

## Support

[Your support info]
