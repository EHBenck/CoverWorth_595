# CoverWorth

CoverWorth is a personal belongings inventory application. The Django backend
stores users, inventories, items, attachments, and saved values in SQLite. The
NiceGUI frontend provides the browser interface.

## Current features

- Register, sign in/out, and update account details and password.
- Create, switch, rename, and archive owned inventories.
- Add and edit items with categories, condition, quantity, purchase information,
  descriptions, photos, and receipt attachments.
- Create and rename inventory-specific locations, optionally nesting them as
  `Home → Basement`. Assign or clear locations on Add/Edit Item, display them
  on Item Details, and filter the inventory by its real locations.
- Archive unused locations. Move or unassign active items and archive active
  child locations first. Existing historical references are retained.
- Search, sort, and switch inventory views; archive and restore items.
- Preview the eBay valuation prototype, accept an estimate, or enter a manual value.
- Export CSV reports and generate PDF reports.

An explicit manual value takes precedence over an accepted estimate, which takes
precedence over purchase price. Accepting an estimate replaces an active manual
override; previewing or canceling an estimate does not change the saved value.

The current estimator in `backend/inventory_manager/pipeline/poc_valuation.py`
selects **iPhone 13 128GB** comparables. General valuation for arbitrary belongings
is still an upstream limitation. Use purchase information or manual values for
items outside that prototype's scope.

## Prerequisites

Use **Python 3.12**, Git, and two terminals. This is the Python version selected
for the release workflow. The application uses Django and NiceGUI; Node/npm is
not required. Package installation requires access to the Python package index.

The full application's requirements are in `frontend/requirements.txt`, which
includes `backend/requirements.txt`. Install that file into **one environment**
so both servers and the integration tests use the same versions. NiceGUI is
pinned once, at 3.18.0. An older NiceGUI installed in an existing virtual
environment can start a server yet fail the simulated browser tests; run the
version check below before interpreting UI test results.

## Clean clone and setup

The commands below clone `main` for a reviewed release. When validating an
unmerged ticket, check out that branch instead (for example, `CW86-87`).
All commands run from the repository root unless stated otherwise.

### Windows PowerShell

```powershell
git clone --branch main https://github.com/EHBenck/CoverWorth_595.git
cd CoverWorth_595
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r frontend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/check_runtime.py
if (-not (Test-Path backend/.env)) { Copy-Item .env.example backend/.env }
if (-not (Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
```

For an **existing checkout**, create the environment only if it does not exist,
and copy each example only if its destination `.env` is absent. Keep existing
credentials, `backend/db.sqlite3`, and `backend/media/` when updating.

Start the backend from the repository root:

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

Open a second terminal in the repository root and start the frontend:

```powershell
.\.venv\Scripts\python.exe frontend/main.py
```

### macOS / Linux

```bash
git clone --branch main https://github.com/EHBenck/CoverWorth_595.git
cd CoverWorth_595
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r frontend/requirements.txt
.venv/bin/python -m pip check
test -f backend/.env || cp .env.example backend/.env
test -f frontend/.env || cp frontend/.env.example frontend/.env
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000
```

In a second terminal at the repository root:

```bash
.venv/bin/python frontend/main.py
```

Open [CoverWorth](http://127.0.0.1:8080/) and register an account. The backend's
[health endpoint](http://127.0.0.1:8000/api/health/) should return a successful
response. Use the same browser hostname consistently when signing in.

The backend commands also work from `backend/` by using `manage.py` and the
appropriate relative path to the root environment. If your existing environment
is `backend/.venv`, substitute that interpreter path throughout; do not rely on
a second environment being automatically activated.

## Environment variables

No eBay credentials are required to start the application, use local inventory
features, or run the regression tests. Live eBay valuation requires your own
application credentials.

Django loads `backend/.env`. NiceGUI loads `frontend/.env`. Variables already
set in a terminal take precedence over these files. Both files are ignored by
Git. `.env.example` contains backend development defaults and blank eBay fields;
`frontend/.env.example` contains frontend defaults. The examples include all
CoverWorth-specific runtime variable names, with blank optional credentials.

| Variable | Read by | Default / purpose |
| --- | --- | --- |
| `DEBUG` | Django | `True` for local development. |
| `SECRET_KEY` | Django | Public development fallback. Set a private random value for a shared deployment; disabling `DEBUG` without replacing the fallback is rejected. |
| `ALLOWED_HOSTS` | Django | `localhost,127.0.0.1`; comma-separated backend hostnames. |
| `CORS_ALLOWED_ORIGINS` | Django | `http://localhost:8080,http://127.0.0.1:8080`; comma-separated browser origins. |
| `DATABASE_URL` | Django | Optional pooled PostgreSQL/Neon connection URL; blank selects local SQLite. |
| `DATABASE_URL_UNPOOLED` | Django | Optional direct PostgreSQL URL required when `COVERWORTH_DB_DIRECT=True`. |
| `COVERWORTH_DB_DIRECT` | Django | `False`; set `True` while migrating PostgreSQL using the direct URL. |
| `COVERWORTH_S3_BUCKET` | Django storage | Optional S3 bucket; blank uses local `backend/media/` for uploads. |
| `EBAY_CLIENT_ID` | Django valuation pipeline | Blank by default; required only for live eBay calls. |
| `EBAY_CLIENT_SECRET` | Django valuation pipeline | Blank by default; required only for live eBay calls. |
| `COVERWORTH_DEMO_PASSWORD` | `seed_demo` command | Optional; blank generates a password on first seed. Setting it ensures repeatable demo credentials. |
| `BACKEND_URL` | NiceGUI | `http://127.0.0.1:8000`; backend origin without a trailing slash. |
| `NICEGUI_HOST` | NiceGUI | `127.0.0.1`; local bind address. |
| `NICEGUI_PORT` | NiceGUI | `8080`; frontend port. |
| `NICEGUI_STORAGE_SECRET` | NiceGUI | Public development fallback. Set a private random value when sharing the server. |
| `NICEGUI_STORAGE_PATH` | NiceGUI | Framework storage path; tests override it with disposable storage. |
| `EMAIL_HOST` | Django MAILERS | Optional SMTP hostname. Blank uses console-only email in development and disables email delivery when `DEBUG=False`. |
| `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Django MAILERS | SMTP connection; defaults 587 / True / False. TLS and SSL are mutually exclusive. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Django MAILERS | SMTP credentials if required by the selected provider. |
| `EMAIL_TIMEOUT` | Django MAILERS | SMTP network timeout in seconds (10). |
| `DEFAULT_FROM_EMAIL` | Django MAILERS | Sending identity; required when `EMAIL_HOST` is set. |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Django | Defaults False in development, True when `DEBUG=False`. |
| `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Django | HSTS settings; opt in only when all relevant HTTPS routes are confirmed. |
| `COVERWORTH_TRUST_PROXY_SSL_HEADER` | Django | False by default. Enable only for a trusted TLS proxy that strips incoming spoofed forwarding headers. |

If S3 is enabled, the AWS SDK must have credentials/permissions through its
normal environment, profile, or role chain. Do not add AWS secrets to Git.
If you change `NICEGUI_PORT`, update `CORS_ALLOWED_ORIGINS` to match the browser
origin. If you change the backend port, update `BACKEND_URL` accordingly.

To change the API URL for a frontend terminal in PowerShell:

```powershell
$env:BACKEND_URL = "http://127.0.0.1:8000"
```

In macOS/Linux:

```bash
export BACKEND_URL="http://127.0.0.1:8000"
```

Generate a random secret with your environment's Python interpreter:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Place real eBay values only in `backend/.env` or the process environment. Never
paste them into source, fixtures, screenshots, CI YAML, commit messages, or PRs.
Use the credential check below before pushing. It is a focused check of candidate
files; it does not establish that every historical commit is secret-free. If a
credential was ever pushed, revoke/rotate it and coordinate history cleanup.

These commands run development servers. Changing `DEBUG` alone does not configure
a production web server, TLS, static/media serving, or deployment security.
In production, configure HTTPS at the public ingress and use a private
`SECRET_KEY` and correct `ALLOWED_HOSTS`. Secure redirects and cookies default
to True when `DEBUG=False`. If NiceGUI and Django run on the same server and
Django listens only on loopback, NiceGUI can use a loopback HTTP `BACKEND_URL`.
In this setup, enforce HTTPS and secure browser cookies at the public proxy,
and set `SECURE_SSL_REDIRECT=False`, `SESSION_COOKIE_SECURE=False`, and
`CSRF_COOKIE_SECURE=False` for the private Django listener. To enable email
delivery, configure an authenticated SMTP server and an approved sender.
If TLS ends at a reverse proxy, enable `COVERWORTH_TRUST_PROXY_SSL_HEADER` **only**
when the application is unreachable except through a trusted proxy that
sanitizes `X-Forwarded-Proto`. HSTS should remain disabled until HTTPS is
verified. Set `SECURE_HSTS_SECONDS` (for example, `3600`) after verification;
include subdomains or preload **only when their security prerequisites are
satisfied**. Django's deployment check may intentionally retain warnings
until you explicitly make those policy choices. Real mail delivery, S3, TLS,
and hosted PostgreSQL require external-service testing and are not covered by
the local demo instructions.

## Repeatable demo data (CW86)

After running `migrate`, initialize **sample data only** with one Django command
from the repository root:

```powershell
.\.venv\Scripts\python.exe backend/manage.py seed_demo
```

On macOS/Linux, use `.venv/bin/python backend/manage.py seed_demo`.
For a step-by-step Windows walkthrough with both servers and demo login,
see [docs/demo_walkthrough.md](docs/demo_walkthrough.md).
The command creates a `coverworth_demo` user (`demo@coverworth.example`), two
inventories, seven categories, nine nested locations, ten realistic items, and
sample **manual** valuations. All example values are fictional. It does not
call eBay or require external API keys. If you leave
`COVERWORTH_DEMO_PASSWORD` blank in `backend/.env`, the command prints a
random login password **once** when the user is first created. Store it
locally; reruns with a blank password preserve it. For consistent demo logins,
set a private `COVERWORTH_DEMO_PASSWORD` in your untracked `backend/.env` before
seeding. The username is always `coverworth_demo`. Supplying a different
`COVERWORTH_DEMO_PASSWORD` on a subsequent seed **changes the existing demo
user's password**. With the setting blank, an existing password is preserved.
If you lost the password, use `python backend/manage.py changepassword
coverworth_demo` instead of resetting the database.

Running the same command again refreshes the seeded fields and **does not**
create duplicate sample items, inventories, or valuation runs. It leaves any
extra records you added alone. For a pristine walkthrough, use:

```powershell
.\.venv\Scripts\python.exe backend/manage.py seed_demo --reset
```

`--reset` **deletes all contents of the two demo inventories** and recreates
those inventories. It does not delete the demo login, other inventories owned
by that login, or other users' data. It is intentionally disabled when
`DEBUG=False`; on a development PostgreSQL database the command additionally
requires `--allow-remote-db`. **Never run it against real user data.**

## Shared PostgreSQL on Neon

Neon hosts PostgreSQL. Run Django and NiceGUI on the application host.
Run `neon deploy` from the repository root to pull the linked branch's
`DATABASE_URL` and `DATABASE_URL_UNPOOLED` into the root `.env` or
`.env.local`. Django reads that file after `backend/.env`. For a hosted
Django process, set both URLs in the host's secret settings. Keep the eBay
credentials in Django's environment as well. The frontend connects through
`BACKEND_URL`. Local development uses SQLite when `DATABASE_URL` is unset.

For the initial schema or later migrations, use the direct connection. From
the repository root with the project virtual environment active in PowerShell:

```powershell
$env:COVERWORTH_DB_DIRECT = 'True'
python backend/manage.py migrate --noinput
Remove-Item Env:COVERWORTH_DB_DIRECT
```

Start Django without that flag to use the pooled URL. Migrations create or
update the PostgreSQL schema. Existing SQLite records require a separate
data transfer.

With the Python dependencies installed and the virtual environment active,
`npm run build` compiles the Python sources and runs Django's system check.
On PowerShell systems that block `npm.ps1`, use `npm.cmd run build`.

## Tests and release checks

Run all required local gates from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/check_release.py
```

For macOS/Linux, substitute `.venv/bin/python` for the PowerShell interpreter.
The gate stops on any failure and performs:

1. Supported Python 3.12 and pinned Django/NiceGUI versions.
2. Installed dependency consistency (`pip check`).
3. Candidate-file environment/eBay credential checks.
4. Django system checks and model/migration consistency checks.
5. All backend regression tests, including Sprint 7 integration coverage.
6. All frontend/API integration tests.
7. Fresh database migrations and real backend/frontend HTTP startup.

Individual commands, using an activated environment for brevity:

```bash
python scripts/check_secrets.py
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
cd ../frontend
python -m pytest -v --durations=10
cd ..
python scripts/smoke_start.py
```

The Django tests create a fresh test database. Frontend integration tests start
an isolated backend, use a temporary database/media/storage directory, and drive
NiceGUI pages with the simulated-user fixture. eBay responses are mocked by
fixtures; the tests do not make live valuation calls. `smoke_start.py` starts
both real entry points with disposable storage and checks HTTP readiness. It is
a startup check, not a browser-based visual acceptance test.

Release approval requires the complete gate on the exact candidate, including
`pip check` after installing the pinned requirements in a fresh environment.
Run the release checks against the exact candidate branch and inspect the
results before merging.

An optional **manual live eBay check** is separate from the release gates and
requires your credentials:

```bash
cd backend
python manage.py shell -c "import runpy; runpy.run_module('inventory_manager.pipeline.test_live', run_name='__main__')"
```

GitHub Actions runs the same required backend/frontend checks and a clean
checkout startup check. Frontend failures no longer count as success. Configure
`Sprint 7 release gate` as a required status check on `main` and `test-env`; the
workflow file alone does not change branch protection.

## Updating an existing development checkout

Commit or stash your work before switching branches. Fetch and pull the branch
you intend to use, reinstall `frontend/requirements.txt`, and run migrations.
Never delete the existing database to make a migration warning disappear.

For a clean-clone check, repeat the setup steps above in an empty directory,
then run the release checks before promoting the branch to `main`.
