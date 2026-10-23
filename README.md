## Development Setup

This project contains:

* **Backend:** Python / Django
* **Frontend:** Python / NiceGUI

### 1. Prerequisites

Before cloning the project, install Git and Python 3.

Check the installations:

	git --version
	python --version

On Windows, if `python` does not work, try:

	py --version

### 2. Clone the Repository

	git clone <YOUR-GITHUB-REPOSITORY-URL>
	cd <YOUR-PROJECT-FOLDER>

If you already cloned the repository:

	git pull

### 3. Backend Setup

Navigate to the backend and create a virtual environment:

	cd backend
	py -m venv .venv

Install the Python dependencies:

	.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Run the Django API server:

	.\.venv\Scripts\python.exe manage.py migrate
	.\.venv\Scripts\python.exe manage.py runserver

The API will be available at http://127.0.0.1:8000/.

### 4. NiceGUI Frontend

Open a second terminal, navigate to the frontend, and start NiceGUI:

	cd frontend
	..\backend\.venv\Scripts\python.exe main.py

The frontend will be available at http://127.0.0.1:8080/.

The frontend uses `BACKEND_URL` when set; otherwise it calls
http://127.0.0.1:8000. For example:

	$env:BACKEND_URL = "http://127.0.0.1:8000"

After pulling changes, reinstall dependencies if `backend/requirements.txt`
changed.

Do not commit `backend/.venv/`.

### 5. Running Tests

Backend unit and API workflow tests (each test uses a fresh test database):

	cd backend
	.\.venv\Scripts\python.exe manage.py test

The tests never call eBay: valuation tests replace eBay's HTTP calls with the
recorded listings in `backend/inventory_manager/fixtures/raw`, so no eBay
credentials are needed. One test is an expected failure that tracks a known
bug: an accepted valuation does not become the item's displayed value.

Frontend <-> backend integration tests. These start their own Django server
on a temporary, freshly migrated database and drive the NiceGUI pages
through NiceGUI's simulated user, so no servers need to be running and
`db.sqlite3` is not touched. That server answers eBay calls from
`frontend/tests/fake_ebay.py` and stores uploads in a temporary folder:

	cd frontend
	..\backend\.venv\Scripts\python.exe -m pytest

To check the real eBay connection by hand (needs `EBAY_CLIENT_ID` and
`EBAY_CLIENT_SECRET` in `backend/.env`):

	cd backend
	.\.venv\Scripts\python.exe -m inventory_manager.pipeline.test_live