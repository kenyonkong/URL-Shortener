# SQLite URL shortener

A minimal React/Vite frontend and FastAPI backend that creates persistent short
URLs and counts visits.

## Setup

Prerequisites: Node.js 20.19+ (or 22.12+) with npm, and Python 3.11 or newer.

Create and prepare the backend environment:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

## Run

Start the API from the repository root:

```powershell
backend/.venv/Scripts/python -m uvicorn main:app --app-dir backend --reload --port 8000
```

In a second terminal, start Vite:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to FastAPI at `http://127.0.0.1:8000`. The API health endpoint is `GET http://127.0.0.1:8000/api/health`.

Enter an HTTP or HTTPS URL in the form. The frontend sends it to
`POST /api/shorten`, and the returned short link redirects to the original URL.
The table loads all saved URL pairs from `GET /api/urls`.
Each short URL allows five successful visits, configured by the global
`MAX_VISITS` value in `backend/main.py`. Later visits receive HTTP `429` instead
of redirecting.

The POST body:

```json
{"url": "https://example.com/a/long/path"}
```

The HTTP `201` response:

```json
{
  "original_url": "https://example.com/a/long/path",
  "shortened_url": "http://127.0.0.1:8000/aB3dE9z",
  "short_code": "aB3dE9z",
  "access_count": 0
}
```

## Database

SQLite creates `backend/url_shortener.db` on the first backend startup. The
file is not deleted or recreated during later startups, so all links and counts
persist. The `urls` table contains:

- `id`: integer primary key
- `original_url`: unique destination URL
- `short_code`: unique random seven-character code
- `access_count`: number of successful short-link requests
- `created_at`: creation time in UTC

Inspect the rows with the SQLite CLI:

```powershell
sqlite3 backend/url_shortener.db "SELECT id, original_url, short_code, access_count, created_at FROM urls;"
```

If the SQLite CLI is not installed, use Python:

```powershell
python -c "import sqlite3; c=sqlite3.connect('backend/url_shortener.db'); c.row_factory=sqlite3.Row; [print(dict(r)) for r in c.execute('SELECT * FROM urls')]"
```

Set `URL_SHORTENER_DB` before starting the backend to use a different database
file.

## Checks

```powershell
backend/.venv/Scripts/python -m unittest discover -s backend -p "test_*.py"
backend/.venv/Scripts/python -m compileall backend
cd frontend
npm run build
```

