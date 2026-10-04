# Truck Trip Planner

A minimal full-stack starter with a Django REST Framework backend and a React app powered by Vite.

## Backend

From the project root, create and activate a virtual environment, install dependencies, and run migrations:

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The health endpoint is available at <http://127.0.0.1:8000/api/health/>.

## Frontend

In a separate terminal, from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually <http://localhost:5173/>).
