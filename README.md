## Development Setup

This project contains:

* **Backend:** Python / Django
* **Frontend:** React / Vite / Node.js

### 1. Prerequisites

Before cloning the project, make sure you have the following installed:

* Git
* Python 3
* Node.js 
* npm — included automatically with Node.js

Check whether they are already installed:


git --version
python --version
node --version
npm --version

On Windows, if `python` does not work, try:

powershell
py --version


If `node` or `npm` is not recognized, install Node.js before continuing.

-------

## 2. Clone the Repository

git clone <YOUR-GITHUB-REPOSITORY-URL>
cd <YOUR-PROJECT-FOLDER>


If you already cloned the repository:


git pull

----

## 3. Backend Setup

Navigate to the backend:

cd backend


Create a Python virtual environment:

py -m venv .venv


Install the backend dependencies:

.\.venv\Scripts\python.exe -m pip install -r requirements.txt


Run the Django development server:

.\.venv\Scripts\python.exe manage.py runserver


The backend will usually be available at:

http://127.0.0.1:8000/


---

## 4. Frontend Setup

Open another terminal and navigate to the frontend:

cd frontend


Install all frontend dependencies:

npm ci


This reads `package.json` and installs the required packages into `node_modules`.

Start the Vite development server:

npm run dev


Vite will display the local development URL in the terminal, usually:

http://localhost:5173/


---

## Starting the Project After Initial Setup

You only need to create the virtual environment and run `npm ci` the first time, or whenever dependencies change.

### Terminal 1 — Backend


cd backend
python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver


### Terminal 2 — Frontend

cd frontend
npm ci
npm run dev


---

## After Pulling New Changes

Update your local repository:

git pull


If backend dependencies may have changed:

cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt


If frontend dependencies may have changed:

cd frontend
npm ci


Then start both servers normally.

---

## Important

Do **not** commit the following folders:

backend/.venv/
frontend/node_modules/