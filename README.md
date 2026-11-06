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
pinned once, at 2.24.2.

## Clean clone and setup

The commands below clone `main` for a reviewed release. The replacement archive
already records promotion of the previous integration build. This CW74/CW80 patch
is a follow-up: its fixes and updated setup instructions become available from a
new clone of `main` after the follow-up PR is tested and merged. See the
[release procedure and candidate validation status](docs/release.md).

### Windows PowerShell

```powershell
git clone --branch main https://github.com/EHBenck/CoverWorth_595.git
cd CoverWorth_595
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r frontend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
Copy-Item .env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
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
cp .env.example backend/.env
cp frontend/.env.example frontend/.env
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
`frontend/.env.example` contains the optional frontend defaults.

| Variable | Read by | Default / purpose |
| --- | --- | --- |
| `DEBUG` | Django | `True` for local development. |
| `SECRET_KEY` | Django | Public development fallback. Set a private random value for a shared deployment; disabling `DEBUG` without replacing the fallback is rejected. |
| `ALLOWED_HOSTS` | Django | `localhost,127.0.0.1`; comma-separated backend hostnames. |
| `CORS_ALLOWED_ORIGINS` | Django | `http://localhost:8080,http://127.0.0.1:8080`; comma-separated browser origins. |
| `EBAY_CLIENT_ID` | Django valuation pipeline | No default; optional, required only for live eBay calls. |
| `EBAY_CLIENT_SECRET` | Django valuation pipeline | No default; optional, required only for live eBay calls. |
| `BACKEND_URL` | NiceGUI | `http://127.0.0.1:8000`; backend origin without a trailing slash. |
| `NICEGUI_HOST` | NiceGUI | `127.0.0.1`; local bind address. |
| `NICEGUI_PORT` | NiceGUI | `8080`; frontend port. |
| `NICEGUI_STORAGE_SECRET` | NiceGUI | Public development fallback. Set a private random value when sharing the server. |
| `NICEGUI_STORAGE_PATH` | NiceGUI | Framework storage path; tests override it with disposable storage. |

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

## Tests and release checks

Run all required local gates from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/check_release.py
```

For macOS/Linux, substitute `.venv/bin/python` for the PowerShell interpreter.
The gate stops on any failure and performs:

1. Installed dependency consistency (`pip check`).
2. Candidate-file environment/eBay credential checks.
3. Django system checks and model/migration consistency checks.
4. All backend regression tests, including Sprint 7 integration coverage.
5. All frontend/API integration tests.
6. Fresh database migrations and real backend/frontend HTTP startup.

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
The [candidate validation snapshot](docs/release.md#candidate-validation-snapshot)
records the observed test results and the checks that remain pending.

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

See [Release procedure](docs/release.md) for version verification, promotion to
`main`, and validation of a clean clone after the merge.
