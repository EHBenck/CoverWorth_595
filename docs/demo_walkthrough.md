# CoverWorth demo walkthrough (Windows PowerShell)

This guide runs a **local-only** demo of CW86/CW87 using SQLite, with no Neon,
S3, or eBay credentials. These commands do not deploy to a hosted server.
All commands start in the CoverWorth repository root. Do not run `seed_demo`
on a shared or production database.

## 1. Open the project and install the required versions

These instructions assume CW86/CW87 patches have been applied to the branch.
If you have uncommitted changes, preserve them before switching branches.

```powershell
git switch CW86-87
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r frontend\requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\check_runtime.py
```

The runtime check must show **Python 3.12**, **Django 6.1.1**, and **NiceGUI
3.18.0**. If `.venv` is an older or incompatible environment, deactivate any
shell using it, rename/remove `.venv`, recreate it with `py -3.12 -m venv
.venv`, and reinstall the requirements. The Django backend and NiceGUI frontend
must use the **same** interpreter.

## 2. Create local configuration and database

```powershell
if (-not (Test-Path backend\.env)) { Copy-Item .env.example backend\.env }
if (-not (Test-Path frontend\.env)) { Copy-Item frontend\.env.example frontend\.env }
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py check
```

For this demo, keep `DEBUG=True`, `DATABASE_URL=` and
`DATABASE_URL_UNPOOLED=` blank in `backend/.env` so SQLite is used.
Make sure your current PowerShell session does not override these with Neon
environment variables. `frontend/.env` should contain
`BACKEND_URL=http://127.0.0.1:8000` and `NICEGUI_PORT=8080`.

## 3. Populate sample data (do this before opening the UI)

```powershell
.\.venv\Scripts\python.exe backend\manage.py seed_demo
```

The seed prints the demo login and inventory totals. On the very first run,
it also prints a **random password once**. Copy that password to a private
password manager. For repeatable credentials you can first add your own
strong, unique `COVERWORTH_DEMO_PASSWORD=...` to the untracked
`backend/.env` instead. Changing that setting and rerunning the command
changes the existing demo user's password. If the password is lost:

```powershell
.\.venv\Scripts\python.exe backend\manage.py changepassword coverworth_demo
```

**To restore the sample inventories** after exploring the UI:

```powershell
.\.venv\Scripts\python.exe backend\manage.py seed_demo --reset
```

`--reset` erases the contents of the two seeded demo inventories. It does
not remove other users or reset the demo password. Seeding is blocked when
`DEBUG=False`; remote development PostgreSQL additionally requires explicit
`--allow-remote-db`. Do not use this on shared data.

## 4. Start the servers in separate PowerShell terminals

**Terminal A — Django API** (leave this open):

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

**Terminal B — NiceGUI frontend** (leave this open):

```powershell
.\.venv\Scripts\python.exe frontend\main.py
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.
Log in with username `coverworth_demo` and your generated or configured
password. Both terminals must stay running while you use the app; use
**Ctrl+C** in each terminal to shut them down. Backend health endpoint:
[http://127.0.0.1:8000/api/health/](http://127.0.0.1:8000/api/health/).

## 5. Suggested 5-minute demo

1. **Dashboard:** review the item and estimated/purchase-value summary for
   the currently selected demo inventory.
2. **Inventories:** use the inventory switcher to change between
   `Demo - Home & Personal` (7 items) and `Demo - Collectibles` (3 items).
3. **Categories and locations:** inspect `Electronics` and nested paths
   including `Home → Office → Desk`; filter items by location.
4. **Items:** open the Dell laptop and Sony headphones. Their values are
   **manual example values**, not live marketplace estimates. Edit an item,
   save changes, and see that it stays in its correct inventory.
5. **Valuations:** review saved manual values. Live eBay estimates require
   separate credentials and are *not* part of the offline demo. The prototype
   supports a limited iPhone 13 comparison; don't promise universal valuations.
6. **Reports:** export the active inventory as CSV or PDF.
7. **Reset:** stop or leave servers running and use `seed_demo --reset` in a
   third terminal to restore sample data. Refresh the browser after resetting.

## 6. Tests and troubleshooting

```powershell
.\.venv\Scripts\python.exe backend\manage.py test myapp.test_seed_demo
.\.venv\Scripts\python.exe -m pytest frontend\tests -q
.\.venv\Scripts\python.exe scripts\check_release.py
```

The full release check runs backend tests, frontend tests, migrations, and
live HTTP smoke tests. Run these with **Python 3.12 and NiceGUI 3.18.0**.
If the backend refuses to start, inspect Terminal A and confirm the
SQLite database was migrated. If login fails, reset the demo password using
`changepassword` above. If the UI doesn't load, check Terminal B, the
NiceGUI version, and whether ports 8000/8080 are already occupied.
If it unexpectedly tries to use Neon, remove `DATABASE_URL` / `DATABASE_URL_UNPOOLED`
from the terminal environment and check `backend/.env` and root `.env` files.

This guide covers local testing, not production readiness. Hosted deployment
also requires TLS, database/storage configuration, and external checks.
Configure SMTP if the hosted environment needs email delivery.
