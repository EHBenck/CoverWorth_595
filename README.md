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