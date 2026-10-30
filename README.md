# Auto Apply

Paste a job link and an agent fills out and submits the application from your profile. When it isn't sure about an answer, it asks you instead of guessing.

**Status:** this is the step 1 skeleton. The screens from our mockup work with sample data, the API saves profiles, answers and applications, and the agent can open a posting and screenshot it. It doesn't fill out forms yet. Look for `TODO(US#)` comments: each one is tagged with the user story it belongs to.

## Stack

| Part | Tech |
| --- | --- |
| Frontend | React 18, Vite 5 |
| API | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 |
| Agent worker | Playwright 1.48 (Chromium) |
| Database | PostgreSQL 16 |
| Dev setup | Docker Compose |

## Run it

With Docker (easiest):

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:5173
- API docs: http://localhost:8000/docs

Without Docker you need Postgres running locally, then:

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload        # API
python -m worker.run                 # agent worker, in a second terminal

# frontend
cd frontend
npm install
npm run dev
```

## Tests and lint

```bash
cd backend
pytest                               # uses a throwaway SQLite db
pylint --rcfile=../.pylintrc app worker
```

CI runs both on every pull request.

## Layout

```
backend/
  app/
    main.py            FastAPI app and routes
    models.py          users, profiles, answers, applications
    routers/           one file per area of the API
    services/ats.py    detects Greenhouse / Lever / Ashby links
  worker/
    run.py             picks up queued applications
    agent.py           Playwright agent (spike: opens + screenshots)
  tests/
frontend/
  src/
    pages/             the six mockup screens
    components/        sidebar, status pill
    api.js             calls to the backend
    mockData.js        sample data until the agent is real
```

See [docs/SKELETON.md](docs/SKELETON.md) for which user stories each file covers.
