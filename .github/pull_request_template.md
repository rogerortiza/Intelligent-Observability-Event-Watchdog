## What was built

<!-- Check each deliverable included in this PR -->

- [ ] <!-- e.g. app/config.py — Pydantic settings with all env vars -->
- [ ] <!-- e.g. app/database.py — sync engine, SessionLocal, init_db() -->

---

## How to test locally

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run unit tests (no DB required)
pytest tests/unit/ -v

# Run integration tests (uses local SQLite)
TEST_DATABASE_URL=sqlite:///./test_watchdog.db pytest tests/integration/ -v

# Start the API (requires .env with SUPABASE_DB_URL)
uvicorn app.main:app --reload

# Run the smoke test against the running API
python tests/smoke_test.py
```

---

## AC verification

<!-- Confirm each acceptance criteria was manually verified before merge -->

| Task | Acceptance Criteria | Verified |
|---|---|---|
| Task XX | <!-- AC from todo.md --> | [ ] |
| Task YY | <!-- AC from todo.md --> | [ ] |

---

## Elapsed time at merge

<!-- Cumulative session time from 2026-06-07 09:48 CST -->

~X hours Y minutes
