# Guidance for AI code contributors (Copilot / agents)

This file gives focused, actionable context for automated or semi-automated code edits in the ArtChaosBot repository.

1. Big picture
- Purpose: a Telegram bot to manage time bookings for a creative studio. Core runtime is a single-process asyncio bot using `python-telegram-bot v20+`.
- Main components:
  - `bot.py` — entrypoint, `ConversationHandler` flow for `/book`, command handlers (`/start`, `/help`, `/add_visits`). Look here for UI text and business-flow decisions (date/time selection, duration parsing, visit debit).
  - `database.py` — SQLAlchemy models and async DB helpers (`init_database`, `get_or_create_user`, `add_booking`, `check_booking_conflict`, `has_booking_on_date`, `add_user_visits`, `decrease_user_visits`). Use these helpers for DB changes.
  - `scheduler.py` — scheduling of reminders via `apscheduler`. `schedule_reminders` is called after a booking is created.

2. Architecture & data flow notes
- Initialization: `bot.py:main()` creates `Application`, starts `AsyncIOScheduler`, sets `application.bot_data['scheduler']`, and calls `init_database()` in `post_init`.
- Booking flow: `/book` → select date (`date_YYYY-MM-DD`) → select time (`time_HH:MM`) → enter duration text → `database.check_booking_conflict()` → `has_booking_on_date()` → optionally `decrease_user_visits()` → `add_booking()` → `schedule_reminders()`.
- DB: tests and code assume SQLite at `bookings.db` via `sqlite+aiosqlite://`. `async_session` is provided by `init_database()`.

3. Project-specific conventions
- Async-first: all DB functions are `async` (use `await`). Bot handlers are `async def` and registered with `python-telegram-bot` `Application`.
- Callback_data patterns: date callbacks use `date_YYYY-MM-DD`, time callbacks `time_HH:MM`. When adding handlers or parsing data, preserve these exact prefixes and formats.
- Business rule: "Day = 1 visit" — only the first booking on a calendar date consumes a visit. The helper `has_booking_on_date(user_id, date)` is used to detect that.
- Admin identity: `ADMIN_TELEGRAM_ID` is read from environment in `bot.py`. Admin checks in `/add_visits` expect this env var (integer Telegram ID). If unset, admin features are disabled.

3.1 Localization convention
- All user-facing strings are centralized in `bot.py` in the `MESSAGES` dictionary. When changing text, update keys in that dict rather than editing strings inline in handlers.

4. Safe edit patterns for agents
- When changing bot messages, keep existing command names (`/book`, `/start`, `/help`, `/cancel`, `/add_visits`) to avoid breaking clients.
- When changing DB models, update `init_database()` and ensure `async_session` usage remains consistent. Prefer adding new migration-safe columns rather than renaming tables.
- When editing reminder scheduling, preserve calls to `schedule_reminders(scheduler, bot, booking, telegram_id)` from `bot.py` so existing flow is unchanged.

5. Common edit examples (copyable snippets)
- Parse callback_data for dates (use in `CallbackQueryHandler`):
  - `date_str = query.data.split('_', 1)[1]`
- Create time button callback payloads (keep `time_` prefix):
  - `InlineKeyboardButton(time_slot, callback_data=f"time_{time_slot}")`

6. How to run / debug locally
- Install deps: `py -m pip install -r requirements.txt` (Windows). The repo uses PowerShell in docs.
- Set token: PowerShell: ``$env:TELEGRAM_TEST_BOT_API="<token>"``. Start: `py bot.py` or `python bot.py`.
- Logging: `logging` is configured in `bot.py`; enable SQLAlchemy SQL logs by setting `echo=True` in `database.py.create_async_engine` when debugging queries.

7. Tests / safety checks for patches
- For handler changes, ensure conversational states remain (SELECTING_DATE, SELECTING_TIME, SELECTING_DURATION) and `ConversationHandler` registration in `main()` is preserved.
- For DB changes, run a quick smoke by invoking `init_database()` and basic helper functions in a small async runner (see `database.test_database()` for example usage).
  - `init_database()` now accepts an optional `db_url` parameter for tests (example: `await init_database(db_url='sqlite+aiosqlite:///test.db')`).

CI/Test snippet:
- Add `pytest` + `pytest-asyncio` for async tests. Example test file: `tests/test_database.py` should create a temporary DB (or use provided `init_database()`), call `add_booking()` and `has_booking_on_date()` and assert expected results.
- Example GitHub Actions workflow: `.github/workflows/ci.yml` that installs deps and runs `pytest` on push/pull_request.
  - Note: current `database.py` uses a hardcoded SQLite URL (`bookings.db`). The provided `tests/test_database.py` is a minimal example; for fully isolated tests prefer refactoring `database.init_database()` to accept a DB URL or use monkeypatching to inject an in-memory or temp DB.

8. Files to check when making changes
- `bot.py` — UI text, handlers, flow control, admin command.
- `database.py` — models and async helpers.
- `scheduler.py` — reminder scheduling logic.
- `README.md` / `ЗАПУСК.md` — update run instructions if you add new environment variables or commands.

9. When not to modify
- Do not change the callback_data prefixes (`date_`, `time_`) without updating all parsing sites.
- Avoid changing synchronous/async boundary patterns (e.g., turning DB helpers to sync) — the app expects async helpers.

If anything here is unclear or you want more examples (tests, common refactors, or a brief CI snippet), tell me what to expand.
