# Support Brain

> **AI-powered customer support platform** — Knowledge Brain, RAG, Gmail integration, Lessons & Feedback Loop.

---

## Overview

Support Brain is a production-ready SaaS platform that lets businesses:

1. Build a **Knowledge Brain** from text, PDFs, and website URLs
2. Deploy a **public AI chat widget** that answers customer questions using RAG
3. Integrate **Gmail** to auto-generate or review email reply drafts
4. Collect **Good/Bad feedback** and auto-create **Lessons** for continuous improvement
5. Use **"Ask This Question Again"** to prove AI learning over time
6. Track everything in a real-time **Analytics dashboard**

---

## Technology Stack

| Layer        | Technology |
|---|---|
| Frontend     | React 18, Vite, Tailwind CSS, Axios, React Router v6, Recharts |
| Backend      | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic v2, Alembic |
| Database     | Supabase PostgreSQL + pgvector |
| AI           | Google Gemini API |
| Email        | Gmail API (OAuth 2.0) |
| Deployment   | Frontend → Vercel · Backend → Render · DB → Supabase |

---

## Gemini Model Selection

> Models verified live against the Google Gemini API v1beta.

| Purpose | Model | Notes |
|---|---|---|
| Text Generation | `gemini-3.8-flash` (or `gemini-flash-latest`) | Current Google production model, replaces deprecated 1.5/2.5 flash |
| Embeddings | `gemini-embedding-001` (with `output_dimensionality=768`) | 768-dim vector projection, replaces deprecated text-embedding-004 |

---

## Database Schema

### Table: `businesses`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(255) | |
| slug | VARCHAR(100) | Unique, indexed — used for public chat URL |
| description | TEXT | |
| is_active | BOOLEAN | |
| created_at / updated_at | TIMESTAMPTZ | |

### Table: `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| email | VARCHAR(255) | Unique |
| hashed_password | VARCHAR(255) | bcrypt |
| full_name | VARCHAR(255) | |
| is_owner | BOOLEAN | |
| is_active | BOOLEAN | |

### Table: `knowledge_sources`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| source_type | ENUM(text,pdf,url) | |
| title | VARCHAR(500) | |
| original_content | TEXT | |
| source_url | TEXT | |
| file_name | VARCHAR(255) | |
| is_processed | BOOLEAN | |
| chunk_count | INTEGER | |

### Table: `knowledge_chunks`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| source_id | UUID FK→knowledge_sources | Indexed |
| chunk_index | INTEGER | |
| content | TEXT | |
| embedding | vector(768) | HNSW index for cosine similarity |
| token_count | INTEGER | |

### Table: `conversations`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| customer_name | VARCHAR(255) | |
| customer_email | VARCHAR(255) | |
| is_resolved | BOOLEAN | |

### Table: `messages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | UUID FK→conversations | |
| business_id | UUID FK→businesses | |
| role | ENUM(user,assistant,system) | |
| content | TEXT | |
| source_chunks | TEXT | JSON array of chunk IDs used |
| lesson_id | UUID FK→lessons | nullable |
| confidence_score | FLOAT | Retrieval-based, not self-reported |

### Table: `pending_questions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| source | ENUM(chat,email) | |
| conversation_id | UUID FK→conversations | nullable |
| email_message_id | UUID FK→email_messages | nullable |
| customer_question | TEXT | |
| status | ENUM(open,resolved) | |
| owner_answer | TEXT | |

### Table: `email_accounts`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Unique with email_address |
| email_address | VARCHAR(255) | |
| encrypted_access_token | TEXT | Fernet-encrypted |
| encrypted_refresh_token | TEXT | Fernet-encrypted |
| processing_mode | ENUM(review,auto) | |
| status | ENUM(connected,disconnected,error) | |

### Table: `email_messages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Multi-tenant isolation |
| email_account_id | UUID FK→email_accounts | |
| gmail_message_id | VARCHAR(255) | Unique — idempotency key |
| gmail_thread_id | VARCHAR(255) | Indexed for email threading |
| direction | ENUM(incoming,outgoing) | |
| related_message_id | UUID FK→email_messages | Points to incoming email for outgoing replies (`uq_email_reply_outgoing` partial unique index) |
| sender / recipient | VARCHAR(255) | Email addresses |
| subject / body_text | TEXT | Stored plain-text and HTML body |
| draft_reply | TEXT | AI-generated draft |
| status | ENUM(pending,draft,sent,failed,skipped) | Current email state |
| sent_at / received_at | TIMESTAMPTZ | Precise send/receive timestamps |

### Table: `lessons`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| question | TEXT | |
| original_answer | TEXT | |
| corrected_answer | TEXT | |
| owner_comment | TEXT | |
| is_active | BOOLEAN | |
| embedding | vector(768) | HNSW index |
| usage_count | INTEGER | |

### Table: `answer_feedback`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | |
| conversation_id | UUID FK→conversations | |
| message_id | UUID FK→messages | |
| feedback_type | ENUM(good,bad) | |
| correct_answer | TEXT | Provided on bad feedback |
| lesson_id | UUID FK→lessons | Auto-linked if lesson created |

### Table: `lesson_usage`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| business_id | UUID FK→businesses | Indexed |
| lesson_id | UUID FK→lessons | Indexed |
| conversation_id | UUID FK→conversations | nullable |
| question | TEXT | The question that triggered the lesson |
| created_at | TIMESTAMPTZ | |

### Table: `email_processing_logs`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | Unique log entry identifier |
| business_id | UUID FK→businesses | Indexed, multi-tenant isolation |
| email_account_id | UUID FK→email_accounts | nullable, indexed |
| gmail_message_id | VARCHAR(255) | nullable, indexed |
| action | VARCHAR(100) | Action executed: fetch, draft_generated, auto_sent, moved_to_pending, error |
| status | VARCHAR(50) | Execution outcome: success, failed, skipped |
| details | TEXT | Detailed diagnostic message or payload details |
| created_at | TIMESTAMPTZ | Timestamp of log event, indexed |


---

## Project Structure

```
support-brain/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, middleware, lifespan
│   │   ├── config.py         # Pydantic settings + startup validation
│   │   ├── database.py       # Async SQLAlchemy engine + pgvector init
│   │   ├── models/
│   │   │   └── models.py     # All 12 SQLAlchemy models
│   │   ├── schemas/
│   │   │   ├── auth.py       # Auth request/response schemas
│   │   │   ├── knowledge.py  # Knowledge schemas
│   │   │   ├── chat.py       # Chat + feedback schemas
│   │   │   ├── email_schema.py
│   │   │   └── lessons.py    # Lessons + analytics schemas
│   │   ├── routes/
│   │   │   ├── auth.py       # /api/auth/*
│   │   │   ├── knowledge.py  # /api/knowledge/*
│   │   │   ├── chat.py       # /api/chat, /api/conversations, /api/feedback
│   │   │   ├── email_routes.py # /api/email/*
│   │   │   ├── pending.py    # /api/pending/*
│   │   │   ├── lessons.py    # /api/lessons/*
│   │   │   └── analytics.py  # /api/analytics/*
│   │   ├── services/
│   │   │   ├── knowledge_service.py  # PDF, URL, text ingestion
│   │   │   └── chat_service.py       # RAG pipeline + feedback
│   │   ├── ai/
│   │   │   ├── gemini_client.py  # Gemini text gen + embeddings
│   │   │   └── search.py         # pgvector semantic search
│   │   ├── email/
│   │   │   └── gmail_service.py  # OAuth + fetch + send
│   │   └── utils/
│   │       ├── auth.py           # JWT + password utils
│   │       ├── encryption.py     # Fernet token encryption
│   │       └── text_processing.py # Chunking + cleaning
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial.py
│   ├── tests/
│   │   ├── test_main.py                              # Core utilities, JWT, bcrypt, chunking, encryption
│   │   ├── test_phase2_auth.py                       # Multi-tenant auth & widget token issuance
│   │   ├── test_phase2_full_two_businesses.py        # Two-tenant credential & resource isolation
│   │   ├── test_phase4_knowledge.py                  # Text, PDF, URL ingestion & chunking
│   │   ├── test_phase5_6_rag.py                      # RAG pipeline, pgvector, citations, fallback
│   │   ├── test_phase7_8_9_continuous_learning.py   # Pending questions, lessons, feedback loop
│   │   ├── test_phase10_11_email.py                  # Gmail OAuth, Review/Auto modes, thread tracking
│   │   └── test_email_safety.py                      # Comprehensive Email Safety, Duplicate Prevention (8 Scenarios)
│   ├── requirements.txt
│   ├── pytest.ini        # Pytest configuration with pythonpath = .
│   ├── alembic.ini
│   └── render.yaml
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── hooks/useAuth.jsx
│   │   ├── services/api.js
│   │   ├── layouts/DashboardLayout.jsx
│   │   └── pages/
│   │       ├── LoginPage.jsx
│   │       ├── RegisterPage.jsx
│   │       ├── DashboardPage.jsx
│   │       ├── KnowledgePage.jsx
│   │       ├── ConversationsPage.jsx
│   │       ├── PendingPage.jsx
│   │       ├── EmailPage.jsx
│   │       ├── LessonsPage.jsx
│   │       ├── AnalyticsPage.jsx
│   │       ├── SettingsPage.jsx
│   │       └── ChatWidgetPage.jsx
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── vercel.json
│
├── widget/
│   ├── src/
│   │   └── widget.js         # Embeddable script for customer websites
│   └── package.json
│
├── .env.example
├── .gitignore
└── README.md
```

---

## Email Safety & Duplicate Reply Prevention Architecture

Support Brain implements a multi-layer defense-in-depth safety mechanism to guarantee that no customer email can ever receive duplicate responses:

1. **Frontend Guarding**:
   - The Send button transitions to an in-flight loading spinner immediately upon being clicked.
   - Once sent, the draft editor is replaced by a verified badge: `✓ Reply sent in thread · Duplicate send prevented`.
   - The state persists across page refreshes from the backend message status.

2. **Atomic Row-Level Database Locking**:
   - The backend acquires an exclusive row lock (`with_for_update()`) on the incoming `EmailMessage` record within the transaction.
   - Concurrent requests for the same email are serialized. The first request completes and marks the status as `sent`, while subsequent requests unblock, detect `status == sent`, and are rejected with HTTP 400 (`This email has already been replied to. Duplicate sending is not allowed.`).

3. **Database-Level Partial Unique Index**:
   - The database enforces `uq_email_reply_outgoing UNIQUE (related_message_id) WHERE direction = 'outgoing'`.
   - PostgreSQL mathematically disallows more than one outgoing reply referencing the same incoming email message.

4. **Uncertain-State Reconciliation with Gmail**:
   - If an uncertain state occurs (e.g., network failure after Gmail API sent the reply but before the DB committed), Support Brain reconciles with the Gmail thread before attempting any send.
   - If the thread already contains a sent message from the business address referencing the incoming message ID, Support Brain updates the DB status to `sent` and aborts duplicate sending.

---

## Environment Setup

### Required Variables

Copy `.env.example` to `backend/.env` and fill in:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `DATABASE_URL` | Supabase → Project Settings → Database → Connection String |
| `GMAIL_CLIENT_ID` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 Client |
| `GMAIL_CLIENT_SECRET` | Same as above |
| `GMAIL_REDIRECT_URI` | `http://localhost:8000/api/email/oauth/callback` (dev) |
| `APP_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `TOKEN_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `FRONTEND_URL` | `http://localhost:5173` (dev) or your Vercel URL |
| `BACKEND_URL` | `http://localhost:8000` (dev) or your Render URL |

---

## Installation & Running

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at: http://localhost:5173

---

## Gmail OAuth Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Gmail API**
4. Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Add Authorised redirect URI: `http://localhost:8000/api/email/oauth/callback`
7. Copy Client ID and Secret to your `.env`

---

## Supabase Configuration

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Database → Extensions** and enable **vector**
3. Go to **Settings → Database** and copy the **Connection string** (URI format)
4. Paste into `DATABASE_URL` in your `.env`
5. Run `alembic upgrade head` to create all tables

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register business + owner |
| POST | `/api/auth/login` | No | Login, returns JWT |
| GET | `/api/auth/me` | Yes | Current user info |
| GET | `/api/knowledge/sources` | Yes | List knowledge sources |
| POST | `/api/knowledge/text` | Yes | Add text |
| POST | `/api/knowledge/pdf` | Yes | Upload PDF |
| POST | `/api/knowledge/url` | Yes | Scrape URL |
| DELETE | `/api/knowledge/sources/{id}` | Yes | Delete source |
| POST | `/api/chat` | No | Public chat (rate-limited) |
| GET | `/api/conversations` | Yes | List conversations |
| POST | `/api/feedback` | Yes | Submit good/bad feedback |
| POST | `/api/ask-again` | Yes | Re-run question |
| GET | `/api/email/oauth/url` | Yes | Get Gmail OAuth URL |
| GET | `/api/email/oauth/callback` | No | OAuth callback |
| POST | `/api/email/fetch` | Yes | Fetch new emails |
| POST | `/api/email/messages/send` | Yes | Send email reply |
| GET | `/api/pending/` | Yes | List pending questions |
| POST | `/api/pending/{id}/resolve` | Yes | Resolve pending question |
| GET | `/api/lessons/` | Yes | List lessons |
| POST | `/api/lessons/` | Yes | Create lesson |
| GET | `/api/analytics/summary` | Yes | Analytics summary + weekly trends |
| GET | `/api/widget/{slug}` | No | Chat widget config |
| GET | `/api/health` | No | Health check |

---

## Testing

The test suite covers the complete application lifecycle across **7 specialized test suites**, ranging from low-level crypto utilities up to end-to-end multi-tenant RAG and Gmail pipelines.

### Running Tests

```bash
cd backend

# Run all 8 test suites (automatically discovers app module via pytest.ini)
pytest tests/ -v

# Or run via Python module mode (cross-platform compatible on Windows/Linux/macOS)
python -m pytest tests/ -v

# Run the comprehensive Email Safety & Duplicate Reply Prevention test suite
pytest tests/test_email_safety.py -v

# Run with short traceback on failure and stop at the first error
pytest tests/ -v -x --tb=short
```

### Test Suites Breakdown

| Test Suite | Purpose & Coverage | Key Assertions / Examples |
|---|---|---|
| **1. `test_main.py`** | Baseline smoke tests and core security/processing utilities. | • Bcrypt password hashing & verification<br>• JWT creation and payload decoding<br>• Text chunking (`chunk_size=100`, `overlap=10`)<br>• Fernet token encryption & decryption roundtrips |
| **2. `test_phase2_auth.py`** | Multi-tenant authentication, token issuance, and protected endpoints. | • Owner registration with auto-generated `widget_token` (`sb_pub_...`)<br>• JWT login and authenticated `/api/auth/me` verification<br>• Access control guards on dashboard routes |
| **3. `test_phase2_full_two_businesses.py`** | Strict cross-tenant data isolation and security boundary verification. | • Simultaneous registration of **Business Alpha** and **Business Beta**<br>• Proves Alpha's JWT token cannot query or modify Beta's workspace<br>• Verifies tenant database query filtering |
| **4. `test_phase4_knowledge.py`** | Multi-format Knowledge Brain ingestion pipeline. | • Plain text document chunking & database persistence<br>• Multi-page PDF text extraction using PyMuPDF (`fitz`)<br>• Website URL ingestion with SSRF protection against internal IPs |
| **5. `test_phase5_6_rag.py`** | Public customer chat widget and RAG pipeline. | • Serving `/widget.js` embed script with CORS headers<br>• Vector semantic search with `pgvector`<br>• Grounded answer generation with source chunk citations<br>• Unknown-question fallback to `"Thank you! The team will reply to you soon."` |
| **6. `test_phase7_8_9_continuous_learning.py`** | Closed-loop self-learning system and feedback. | • Automatic Pending Question creation on low confidence<br>• Owner answer resolution via "Add answer to Brain"<br>• Automatic Lesson generation from "Bad" feedback<br>• "Ask This Question Again" side-by-side comparison |
| **7. `test_phase10_11_email.py`** | Gmail integration and autonomous email pipeline. | • Gmail OAuth 2.0 URL generation and callback handling<br>• **Review Mode**: AI-generated drafts with owner approval<br>• **Auto Mode**: High-confidence automated replies<br>• Thread preservation (`In-Reply-To`, `References`) and duplicate reply prevention |
| **8. `test_email_safety.py`** | Comprehensive Email Safety, Duplicate Prevention, and History suite. | • **Test 1**: Polling idempotency (no duplicate incoming records on re-fetch)<br>• **Test 2**: Review Mode draft generation without auto-send<br>• **Test 3**: Review Mode dispatch & thread preservation<br>• **Test 4**: Strict duplicate reply rejection (HTTP 400)<br>• **Test 5**: Concurrency race condition prevention (`asyncio.gather` with DB row lock)<br>• **Test 6**: Email history with complete metadata (`direction`, `related_message_id`, timestamps)<br>• **Test 7**: Multi-tenant email history isolation across businesses<br>• **Test 8**: Uncertain Gmail send state reconciliation before retrying |

### Example Test Commands

```bash
# 1. Test Multi-Tenant Authentication & Isolation
pytest tests/test_phase2_auth.py tests/test_phase2_full_two_businesses.py -v

# 2. Test Knowledge Brain Ingestion & Chunking
pytest tests/test_phase4_knowledge.py -v

# 3. Test RAG Search & Chat Grounding
pytest tests/test_phase5_6_rag.py -v

# 4. Test Lessons, Pending Questions & Feedback Loop
pytest tests/test_phase7_8_9_continuous_learning.py -v

# 5. Test Gmail Integration & Email Pipeline
pytest tests/test_phase10_11_email.py -v

# 6. Test Email Safety, Concurrency & History (All 8 Scenarios)
pytest tests/test_email_safety.py -v
```

---

## Deployment

### Backend (Render)

1. Push to GitHub
2. Create a new **Web Service** on Render
3. Root directory: `backend`
4. Build: `pip install -r requirements.txt`
5. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables from `.env.example`
7. Run migrations: `alembic upgrade head` (in Render Shell)

### Frontend (Vercel)

1. Push to GitHub
2. Import project on Vercel
3. Root directory: `frontend`
4. Framework: Vite
5. Build: `npm run build`
6. Add env var: `VITE_API_URL=https://your-backend.onrender.com/api`
7. Deploy

---

## Security

- Passwords hashed with bcrypt (passlib)
- JWT tokens signed with HS256
- Gmail tokens encrypted at rest with Fernet symmetric encryption
- All knowledge/conversation/email queries filtered by `business_id`
- CORS restricted to configured frontend URLs
- Public chat endpoint rate-limited (30 req/min per IP)
- File upload: type validation + 10MB size limit
- SQL injection prevented by SQLAlchemy parameterised queries
- Environment secrets never logged or committed

---

## Confidence Scoring

The AI confidence score is **not** self-reported by the LLM. It is calculated from:

1. **Top cosine similarity** of retrieved knowledge chunks (primary signal)
2. Whether the answer equals the fallback phrase (score = 0.0)
3. Lesson matches receive a minimum score of 0.90

Threshold: `0.75` — answers below this trigger a Pending Question automatically.
