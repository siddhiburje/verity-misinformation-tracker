# Verity — AI-Based Misinformation Evolution Tracker Using NLP

A full-stack web app that traces how a claim changes across sources and
time. Paste text, upload a screenshot, or search a live news topic —
Verity runs real NLP (TF-IDF similarity, spaCy NER, TextBlob sentiment,
DBSCAN clustering) to compare it against everything already tracked,
and renders the result as an interactive evolution graph + timeline.

Built as a college mini-project. Every score, cluster, and graph edge
shown in the UI is computed live from the NLP pipeline — nothing is
hard-coded or decorative.

---

## 1. Feature checklist

| Area | Status |
|---|---|
| Landing page | ✅ real pipeline explanation, worked example, CTA |
| Sign up / log in / log out | ✅ JWT-based, bcrypt-hashed passwords, protected routes |
| Text input analysis | ✅ paste article/claim/headline |
| Image input + OCR | ✅ PNG/JPG/WEBP → Tesseract OCR → shown to user → NLP |
| Live news search & tracking | ✅ NewsAPI, honest offline fallback if no key |
| NLP: keywords | ✅ TF-IDF, lemmatized |
| NLP: named entities | ✅ spaCy `en_core_web_sm` |
| NLP: sentiment | ✅ TextBlob polarity/subjectivity |
| NLP: similarity | ✅ cosine similarity over shared TF-IDF space |
| NLP: clustering | ✅ DBSCAN (batch import) + threshold graph (per-claim) |
| Claim verification | ✅ Google Fact Check Tools API, separate from narrative matching — see §4b |
| Evolution graph | ✅ interactive SVG: pan, zoom, click-to-select |
| Timeline | ✅ chronological, linked to graph selection |
| Source analysis | ✅ name, date, URL, narrative per source |
| Dataset import (CSV/TXT) | ✅ client-side parse → real batch NLP analysis |
| Search history | ✅ per-user, clickable to reopen results |
| Responsive design | ✅ tested at desktop + mobile (390px) viewports |
| Error handling | ✅ every endpoint returns a clear message, never a blank page |

---

## 2. Project structure

```
verity/
├── backend/
│   ├── app.py                  # Flask app factory, page routes, error handlers
│   ├── config.py                # env-driven configuration
│   ├── extensions.py            # db / jwt / cors singletons
│   ├── models.py                # User, Claim, Relationship, SearchHistory
│   ├── requirements.txt
│   ├── .env.example
│   ├── nlp/
│   │   ├── engine.py             # keywords, NER, sentiment, similarity, clustering
│   │   └── seed_data.py          # curated reference misinformation narratives
│   ├── ocr/
│   │   └── engine.py             # Tesseract OCR wrapper
│   ├── services/
│   │   ├── analysis_service.py   # ties DB + NLP together, builds the graph
│   │   └── news_service.py       # NewsAPI client + offline fallback
│   ├── routes/
│   │   ├── auth.py               # /api/auth/*
│   │   ├── analyze.py            # /api/analyze/*, /api/claims/*, /api/history
│   │   ├── news.py               # /api/news/*
│   │   └── graph.py              # /api/graph/*, /api/evolution/*, /api/sources/*, /api/stats
│   ├── e2e_test.py               # Playwright browser test (see §7)
│   └── instance/                 # SQLite DB lives here (gitignored)
└── frontend/
    ├── templates/
    │   ├── landing.html
    │   ├── auth.html
    │   └── dashboard.html
    └── static/
        ├── css/design-system.css
        └── js/{api.js, graph.js, app.js}
```

Frontend and backend are served from **one Flask app / one origin** —
no separate dev server or CORS setup needed for local use.

---

## 3. Setup

### Requirements
- Python 3.10+
- `tesseract-ocr` system binary (for image OCR)

### Quick start — macOS / Linux

```bash
./setup.sh   # creates venv, installs deps, installs spaCy model, copies .env.example
./run.sh     # starts the server on http://localhost:5000
```

### Quick start — Windows

Double-click `setup.bat` (or run it from Command Prompt), then double-click
`run.bat`. See **§3a below** for a fully spelled-out, step-by-step Windows
walkthrough if you'd rather type each command yourself.

### Manual setup (if you prefer not to use the scripts)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
sudo apt-get install tesseract-ocr   # Ubuntu/Debian; see README §4 for other OS
cp .env.example .env                 # then edit .env
python3 app.py
```

Open **http://localhost:5000**.

---

## 3a. Step-by-step for Windows

**What you need first:**
- [Python 3.10+](https://www.python.org/downloads/) — during install, check **"Add python.exe to PATH"**.
- (Optional, only for image/screenshot analysis) [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) — during install, check **"Add to PATH"** if it's offered. If you miss that checkbox, the app still finds it automatically at its default install location (`C:\Program Files\Tesseract-OCR\tesseract.exe`).

**Steps:**

1. Unzip the project anywhere, e.g. `C:\Users\you\Documents\verity`.
2. Open that exact folder in a terminal:
   - File Explorer → open the `verity` folder → click the address bar → type `cmd` → Enter.
   - (This must be the top-level `verity` folder — the one containing `backend`, `frontend`, `setup.bat`, `run.bat` — not a folder inside it.)
3. Run setup (only needed once):
   ```
   setup.bat
   ```
   This creates a virtual environment in `backend\.venv`, installs all Python packages, downloads the spaCy language model, checks for Tesseract, and creates `backend\.env` from the example file.
4. Start the server:
   ```
   run.bat
   ```
   Leave this window open — it's the running server.
5. Open Chrome and go to:
   ```
   http://localhost:5000
   ```
6. To stop the server, click back into the terminal window running `run.bat` and press `Ctrl+C` (then press `Y` if asked to confirm).

**Optional, configure any time later** by editing `backend\.env` in Notepad:
- `NEWSAPI_KEY` — a free key from https://newsapi.org/register enables *live* news search on the News Tracker page. Without it, that page still works fully, but clearly labels its articles as offline sample data instead of live results.
- `JWT_SECRET_KEY` / `FLASK_SECRET_KEY` — fine to leave as the auto-generated defaults for local/demo use; only matters if you ever deploy this somewhere other than your own machine.
- `TESSERACT_CMD` — only needed if Tesseract is installed somewhere other than the two default locations the app already checks; set it to the full path of `tesseract.exe`.

After editing `.env`, stop the server (`Ctrl+C`) and run `run.bat` again for the change to take effect.

---

## 4. Environment variables (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Required? | Purpose |
|---|---|---|
| `JWT_SECRET_KEY` | Yes (any real deployment) | Signs auth tokens. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_SECRET_KEY` | Yes | Flask session secret |
| `DATABASE_URL` | No | Defaults to a local SQLite file |
| `NEWSAPI_KEY` | **No, but recommended** | Get a free key at https://newsapi.org/register. Without it, the News Tracker page works but clearly labels its results as offline sample data instead of live news. |
| `FACTCHECK_API_KEY` | **No** | Get a free key by enabling the "Fact Check Tools API" on a Google Cloud project. Without it, Claim Verification always returns `Unverified` with an honest explanation instead of guessing — see §4b. |
| `TESSERACT_CMD` | No | Full path to `tesseract`/`tesseract.exe`, only needed if it's installed somewhere the app doesn't already check automatically (see §4a). |
| `CORS_ORIGINS` | No | Only needed if you split frontend/backend onto different ports |

**Tesseract OCR** is a system binary, not a pip package:
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- macOS: `brew install tesseract`
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki — see §4a below

Without it, every other feature still works — only image upload analysis
will return a clear error instead of a result.

### 4a. Tesseract on Windows specifically

The Windows installer doesn't always add `tesseract.exe` to your PATH
(there's a checkbox for it during setup that's easy to miss). If you
skip it, `pytesseract` would normally fail to find the binary at all —
this project works around that automatically: on startup it checks, in
order, the `TESSERACT_CMD` environment variable, your PATH, then the
two default install locations:
```
C:\Program Files\Tesseract-OCR\tesseract.exe
C:\Program Files (x86)\Tesseract-OCR\tesseract.exe
```
If you installed it somewhere else, set `TESSERACT_CMD` in `backend\.env`
to the full path of `tesseract.exe` and restart the server.

### 4b. Claim verification (separate from narrative matching)

Every claim already gets **narrative matching**: "does this look similar,
by text, to other claims already tracked?" (TF-IDF similarity — see
`nlp/engine.py` and `services/analysis_service.py`). That is a
similarity score, never evidence of truth or falsity, and the UI labels
it "Narrative match" for exactly that reason.

**Claim verification** is a separate, additive layer (`services/verification_service.py`,
wired into `POST /api/analyze/text` and `POST /api/analyze/image` only —
not into `/api/analyze/batch`, News Tracker, or the reference dataset).
It asks Google's Fact Check Tools API: "has an independent publisher
actually reviewed this claim, and what did they conclude?" The result is
one of four states, shown in its own "Claim verification" card in the UI:

- **Supported** — one or more fact-check reviews rated the claim true/accurate, none rated it false.
- **Contradicted** — one or more reviews rated it false/misleading, none rated it true.
- **Mixed** — reviews disagreed, or a review's own rating was explicitly partial (e.g. "Half True").
- **Unverified** — the honest default whenever there isn't confident evidence either way. This is returned, with a specific explanation, when:
  - `FACTCHECK_API_KEY` isn't configured,
  - the Fact Check Tools API is unreachable, times out, errors, or rate-limits,
  - the API responds but found no matching fact-check for the claim,
  - the API found results but none had an attributable publisher/URL, or
  - reviews were found but their rating text couldn't be confidently classified.

**Verification never fabricates a source, rating, or verdict.** Every
field shown (publisher, title, rating, URL, date) is copied directly
from the API response; nothing is invented, and "no evidence found" is
never displayed as if it were evidence the claim is true.

**One-time database reset required.** This feature added four new
columns to the existing `claims` table (`verification_status`,
`verification_explanation`, `verification_sources_json`,
`verification_checked_at`). The app creates missing *tables*
automatically on startup but cannot add columns to a table that
already exists, so if you have a `backend/instance/verity.db` from
before this change, delete that one file once and restart the server —
it will be recreated automatically, reference data included. No other
setup step changes.

---

## 5. API reference

All endpoints except `/api/auth/signup` and `/api/auth/login` require
`Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/signup` | Create account → `{token, user}` |
| POST | `/api/auth/login` | Log in → `{token, user}` |
| POST | `/api/auth/logout` | Stateless logout (client discards token) |
| GET | `/api/auth/me` | Current user |
| POST | `/api/analyze/text` | `{text}` → claim + NLP + verification + graph + timeline |
| POST | `/api/analyze/image` | multipart `image` → OCR text + NLP + verification + graph |
| POST | `/api/analyze/batch` | `{items:[{claim,source,date}]}` → dataset results (no verification) |
| GET | `/api/claims/:id` | A single claim (incl. verification, if run) + its neighbor graph |
| GET | `/api/graph/:id` | Raw `{nodes, edges}` centered on a claim |
| GET | `/api/evolution/:id` | Graph + chronologically sorted timeline |
| GET | `/api/sources/:id` | Source metadata for a claim's neighbors |
| GET | `/api/news/search?q=` | Raw NewsAPI search (or offline fallback) |
| POST | `/api/news/track` | `{query}` → ingest articles into the shared graph |
| GET | `/api/history` | Current user's recent searches |
| GET | `/api/stats` | Total claims / clusters tracked (for the Overview page) |
| GET | `/api/nlp/status` | Whether the optional spaCy NER model loaded |
| GET | `/api/health` | Liveness check |

---

## 6. Database

SQLite by default (`backend/instance/verity.db`), created automatically
on first run. Tables: `users`, `claims`, `relationships`,
`search_history` — see `backend/models.py` for full schema and
docstrings. The reference misinformation dataset (`backend/nlp/seed_data.py`)
is seeded automatically into `claims` on first run so the graph/cluster
features have real data from the start. `claims` also stores each
claim's verification result (see §4b) once checked.

**If you have an existing `backend/instance/verity.db` from before the
Claim Verification feature was added,** delete that file once — the new
`verification_*` columns can't be added to an already-existing table
automatically (no migration framework is used, by design, for a
project this size). A fresh `verity.db` is created on the next server
start with no other steps needed.

---

## 7. Testing

Two automated test scripts are included in `backend/`:

```bash
cd backend
python3 e2e_test.py      # full Playwright browser flow: signup → analyze
                          # text/image → import dataset → track news →
                          # history → logout → login → wrong-password error
python3 mobile_test.py   # same flow at a 390px mobile viewport
```

Both drive a real Chromium browser against a real Flask server and
assert on actual rendered DOM state (not mocked). Install Playwright's
browser once with `python3 -m playwright install chromium` if you
haven't already.

Manual testing checklist covered during development:
- [x] Signup/login validation, error states, wrong password, duplicate email
- [x] Protected routes redirect to `/auth` when logged out
- [x] Text analysis produces real similarity scores against seed data
- [x] Image OCR extracts and displays real text before analysis
- [x] Bad image format / oversized file / empty file are rejected with clear errors
- [x] CSV and TXT dataset import, batch NLP analysis
- [x] News search offline fallback banner when `NEWSAPI_KEY` is unset
- [x] Graph pan/zoom/click, timeline click-through, sources list
- [x] History page reopens past results
- [x] Responsive layout at desktop and mobile widths
- [x] Claim verification: missing `FACTCHECK_API_KEY` → honest `Unverified`
- [x] Claim verification: API reachable but no matching fact-check → `Unverified`
- [x] Claim verification: API returns a real matching fact-check → correct status + real source(s) shown
- [x] Claim verification: API failure/timeout → `Unverified`, distinct explanation from "no match found"
- [x] Claim verification never shown for `/api/analyze/batch` results

---

## 8. Team split (3 developers)

- **Frontend / UI / graph visualization** — `frontend/`, especially
  `static/js/graph.js` and `static/css/design-system.css`
- **Backend / API / auth** — `backend/routes/`, `backend/app.py`,
  `backend/extensions.py`
- **NLP / data / database** — `backend/nlp/`, `backend/services/`,
  `backend/models.py`

Each area talks to the others only through the documented API in §5,
so the three parts can be built and tested independently.

### Git workflow
```bash
git init
git add .
git commit -m "Initial Verity implementation"
# create a repo on GitHub, then:
git remote add origin <your-repo-url>
git push -u origin main
```
Branch per feature (`feature/graph-zoom`, `feature/news-tracker`, …),
PR into `main`. `backend/.env` is gitignored — never commit real secrets.

---

## 9. Known limitations

- **NewsAPI free tier** only indexes articles from the last ~30 days
  and has a request-per-day cap; the app degrades to a clearly-labeled
  offline sample when no key is set or the quota is hit — it never
  pretends offline data is live.
- **TF-IDF similarity** is bag-of-words, not semantic embeddings — it
  can miss claims that are worded very differently but mean the same
  thing (a known, documented trade-off for a lightweight NLP pipeline
  in a college project; the code is structured so a future upgrade to
  sentence embeddings only requires changing `nlp/engine.py`).
- **spaCy's `en_core_web_sm`** is a small, fast NER model — it will
  miss or mislabel some entities, especially informally-written text.
- **OCR accuracy** depends on image quality; low-resolution or heavily
  stylized screenshots may extract poorly. The extracted text is always
  shown to the user so this is never silently wrong.
- **Claim verification coverage is inherently incomplete.** The Fact
  Check Tools API only returns results if some publisher has already
  published a formal fact-check of a sufficiently similar claim — most
  claims, especially novel, obscure, or very recently-written ones,
  will legitimately come back `Unverified` simply because no such
  review exists yet. That is the correct, honest result in that case —
  not a bug, and not evidence the claim is true.
- The Flask dev server (`app.py`) is for local/demo use — for a real
  deployment, run behind `gunicorn`/`waitress` and a real web server.


### Verification vs news context
Claim verification uses the Google Fact Check Tools API. Live NewsAPI results are displayed separately as reporting context and are not automatically treated as proof of a claim.
