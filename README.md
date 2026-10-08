# CALARO

**Speak your meal. In your language.**

CALARO is a nutrition tracker built for how India actually eats and talks. Say
*"ரெண்டு இட்லி, ஒரு வடை, ஒரு கிண்ணம் சாம்பார்"* or *"दो रोटी, एक कटोरी दाल"*. CALARO
understands it, matches each dish against a curated Indian food database with
household portions (katori, ladle, tumbler, roti, plate), and **replies out
loud in your language** through Bhashini.

## Why it's different

| | Typical calorie apps | CALARO |
|---|---|---|
| Input | English text or a photo | Voice or text in 12 Indian languages, in any script, plus Tanglish / Hinglish |
| Food knowledge | Western databases, plus LLM guesses | 140 Indian dishes with names in 10 languages, deterministic portion maths |
| Portions | grams / oz | katori, ladle, tumbler, plate, handful, roti count |
| Feedback | Numbers on a screen | A spoken coach reply in your language: calories left today, a protein or fibre nudge |
| Users | Urban, English-first | Also parents, elders and anyone who doesn't type in English |

## How Vaani works

```
mic ─► 16 kHz WAV ─► Bhashini ASR + NMT ─► native text + English
                                         └─► Indian food DB matcher (native script first, English fills gaps)
                                              └─► items, macros and portions ─► coach reply (EN)
                                                   └─► Bhashini NMT + TTS ─► spoken reply in your language
```

* `backend/app/services/bhashini_service.py`: Bhashini pipeline client (config is cached, ASR→NMT and NMT→TTS are chained in one call each)
* `backend/app/services/nutrition_engine.py`: multilingual matcher, number words in 10 languages, Indian units, portion maths
* `backend/app/data/indian_foods.json`: the food database (edit it to add dishes or regional names)
* `backend/app/services/coach.py`: short spoken-friendly feedback
* `backend/app/api/v1/endpoints/vaani.py`: `/vaani/voice`, `/vaani/text`, `/vaani/foods`, `/vaani/today`, `/vaani/speak`, `/vaani/status`
* `frontend/src/components/VaaniLogger.jsx`: language chips, mic, editable items, spoken reply

Text in any script works even without Bhashini keys, because the matcher reads
native script directly. If Ollama is running, it estimates foods that aren't in the
database, and those items are flagged *AI estimate*.

## Roles

| Role | Who | Can |
|---|---|---|
| Super-admin | Only `calaro@admin.calaro.com` (set by `SUPERADMIN_EMAIL`) | Everything an admin can do, plus the **Admin team** page: see every admin, add admins (new account or upgrade an existing one), remove admin rights, read the change log |
| Admin | Anyone the super-admin adds | **Admin console**: usage overview, people list (deactivate or reactivate members), recent meals |
| Member | Everyone who signs up | Log meals, history, profile |

The super-admin account is created on first start with `SUPERADMIN_PASSWORD`. On every start, any other account
holding the super-admin role is demoted to admin. Signing up never creates an admin.

## Database: MongoDB

Collections: `users`, `food_logs`, `password_resets` (OTP codes, auto-deleted when they expire), `audit_log`. Indexes are
created on startup. See `backend/app/models.py` for the document shapes. Local MongoDB, Docker and Atlas all work, so
only `MONGODB_URI` changes between them.

## Setup

1. `copy backend\.env.example backend\.env` (Windows) or `cp backend/.env.example backend/.env`, then set:
   ```
   SUPERADMIN_PASSWORD=<a strong password>
   BHASHINI_INFERENCE_API_KEY=...
   BHASHINI_UDYAT_KEY=...
   SECRET_KEY=<any long random string>
   ```
2. **Docker (recommended):** `copy .env.example .env`, then `docker compose up --build -d`
   * App: http://localhost · API docs: http://localhost/api/v1/openapi.json · MongoDB (this machine only): `mongodb://localhost:27017`
   * Database browser (optional): `docker compose --profile tools up -d`, then http://localhost:8081 (admin / calaro)
3. **Without Docker:** start MongoDB first (`docker run -d -p 27017:27017 --name calaro-mongo mongo:7`, or install MongoDB Community), then
   ```bash
   cd backend && pip install -r requirements-dev.txt && python -m pytest -q && uvicorn app.main:app --reload
   cd frontend && npm install && npm run dev
   ```
4. Check your Bhashini keys: `cd backend && python scripts/check_bhashini.py`

## Monitoring

**Admin console → Monitoring** embeds Grafana, with no second login. It has three views:
- **Traffic & usage**: site and API traffic, error rate, speed, sign-ins, active people, meals by language, Bhashini response time.
- **Logs**: every service's logs, searchable, kept for 14 days.
- **Server health**: CPU, memory, disk, network, which services are up.

How the sign-in works: Caddy asks the API whether the browser holds an admin's monitoring cookie, and Grafana trusts the answer
(auth-proxy mode). The dashboards are generated from `deploy/grafana/build_dashboards.py`.

## Hosting on calaro.online

See **[DEPLOY.md](DEPLOY.md)**: one free Oracle Cloud server, `docker compose up --build -d`, and automatic HTTPS.

## Nutrition data

Values are per typical home-style serving, compiled from common Indian
references (NIN / IFCT 2017 ingredient values and household recipes). They are
estimates. Calibrate against IFCT before any medical or clinical use.

## Stack

React (Vite), Recharts · FastAPI, MongoDB (Motor) · Bhashini (ASR, NMT, TTS) · Caddy · Prometheus, Loki, Alloy, Grafana · optional Ollama

## License

MIT
