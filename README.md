# AgriTech AI Help Portal

A responsive, animated agricultural technology support website for explaining precision farming concepts, crop/weed detection workflows, and common website/API errors. Built for a Software Development final assessment.

**Live website:** `ADD_YOUR_DEPLOYED_HTTPS_URL_HERE`  
**GitHub repository:** `ADD_YOUR_GITHUB_REPOSITORY_URL_HERE`

> Do not submit the placeholders above. Replace them after deployment. Never commit `.env` or live API keys.

## Features

- Responsive animated Home, Knowledge Base, and Error Library pages.
- Floating AI chat widget on every page, including custom 404 and 500 pages.
- 12 starter FAQs stored in SQL and displayed from the database.
- HTTP 400, 401, 403, 404, 429, 500, 503, and custom application code 460.
- FAQ retrieval assistant; optional OpenAI-compatible chat completions integration; retrieval fallback if the key/provider is unavailable.
- Support tickets stored in SQL.
- Chat logs and feedback stored in MongoDB when `MONGODB_URI` is configured.
- `/api/health` health endpoint and request method/path/status/duration logging.
- OpenWeather third-party API integration with explicit connection/request timeouts and fallback.
- Environment variables for all credentials; `.env.example` contains placeholders only.
- Dockerfile and Render blueprint for deployment.

## Stack

FastAPI + Jinja2 + vanilla JavaScript/CSS; SQLAlchemy with SQLite locally or PostgreSQL in deployment; MongoDB Atlas for event logs; optional OpenAI API; OpenWeather API.

## Run locally

Requires Python 3.10+ (Python 3.12 recommended).

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The SQL tables and starter data are created automatically at first startup. For local Windows PowerShell, use `Copy-Item .env.example .env` if `copy` is aliased unexpectedly.

### Environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `DATABASE_URL` | No locally; yes for PostgreSQL deployment | SQL connection string |
| `MONGODB_URI` | For Mongo persistence | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | No | Mongo database name |
| `OPENAI_API_KEY` | Optional | Enables LLM answers; retrieval fallback works without it |
| `OPENAI_MODEL` | No | Model name accepted by your API account |
| `OPENWEATHER_API_KEY` | Optional | Enables live weather; fallback works without it |
| `LOG_LEVEL` | No | Application log verbosity |

## Database model

- `faqs`: question, answer, category.
- `error_codes`: code, title, explanation, solution.
- `support_tickets`: name, email, question, status, created_at.
- MongoDB `events` collection: chat events and feedback events with timestamps.

The application seeds 12 FAQs and 8 error-code records at startup if the tables are empty. Use a persistent PostgreSQL database for deployment; ephemeral local SQLite files are for development only.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/faqs` | FAQs from SQL |
| GET | `/api/errors` | Error library from SQL |
| POST | `/api/chat` | FAQ/error-aware assistant |
| POST | `/api/tickets` | Creates SQL support ticket |
| POST | `/api/feedback` | Stores feedback in MongoDB when configured |
| GET | `/api/weather?city=Coimbatore` | Weather API with timeout and fallback |
| GET | `/api/health` | SQL and Mongo availability status |
| GET | `/404` | Custom 404 page |
| GET | `/500` | Custom 500 page |

Example chat request:
```json
{"message":"What is precision weeding?","session_id":"demo-session"}
```

Example support ticket:
```json
{"name":"Demo user","email":"student@example.com","question":"My crop detection model is missing weeds."}
```

## Deploy to Render

1. Push this project to a GitHub repository.
2. In Render, create a new Blueprint and select the repository containing `render.yaml`.
3. Provision the PostgreSQL database described in the blueprint.
4. In the web service environment settings, add `MONGODB_URI` and optional `OPENAI_API_KEY` and `OPENWEATHER_API_KEY`. Never paste secrets into source code or README.
5. Wait for deployment and test `https://YOUR-SERVICE.onrender.com/api/health`.
6. Add the final HTTPS website URL to this README and your assessment spreadsheet.

Free hosting/database plans and provider availability can change; confirm current limits and whether the chosen plan provides persistent storage before submission. A sleeping free service may take time to wake up.

## MongoDB Atlas setup

Create a database user, allow network access appropriate for your deployment (prefer a restricted allowlist where feasible), copy the driver connection string, and set it as `MONGODB_URI` in Render. Do not commit it. If Mongo is not configured, the app remains usable, but chat/feedback persistence will not meet the assessment requirement until configured.

## Test checklist

- [ ] Home, `/faq`, and `/errors` open on desktop and mobile.
- [ ] Chat widget opens on every page, including `/404` and `/500`.
- [ ] At least 10 FAQs display from `/api/faqs`.
- [ ] Eight error codes display from `/api/errors`.
- [ ] Visit `/this-page-does-not-exist` and confirm the custom 404 page.
- [ ] `/api/health` returns service and SQL status.
- [ ] Ask an FAQ question; try an unknown question and create a ticket.
- [ ] Confirm support ticket rows in SQL.
- [ ] With Mongo configured, confirm chat and feedback events in MongoDB.
- [ ] Test with missing API keys and verify graceful fallback.
- [ ] Test a slow/unavailable weather/AI provider and verify timeout/fallback.
- [ ] Check responsive layout at a narrow mobile viewport.
- [ ] Confirm HTTPS and check browser console for errors.
- [ ] Confirm `.env` is ignored by Git and no secrets appear in repository history.

## Proposed improvement

**Proposed improvement:** Add a field-image upload workflow that lets users upload crop/weed photos and receive a confidence-scored detection result, with a human-review step before any machinery action. This would connect the portal to a practical precision-agriculture workflow while keeping safety controls explicit.

## Safety note

This is an educational support portal, not a substitute for agronomist advice or a certified machinery safety system. Never operate a weeding actuator solely on an unverified AI prediction.
