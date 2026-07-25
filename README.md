# DocuCrew — Backend

FastAPI API for **DocuCrew**, a multi-document intelligence platform powered by CrewAI and RAG.

Users register and log in (JWT in an **httpOnly cookie**), create collections, upload documents (PDF, DOCX, TXT, MD), and ask questions. An **Ingestion Crew** parses and embeds files into **ChromaDB**. A **Query Crew** retrieves, cross-references, synthesizes cited answers, and can flag gaps. Conversation context comes from the last 5 Q&A pairs stored in PostgreSQL.

| Layer | Choice |
| ----- | ------ |
| Framework | FastAPI + Uvicorn |
| Language | Python 3.12+ |
| Package manager | **uv** |
| Database | PostgreSQL (Neon / asyncpg, SSL required) |
| ORM / migrations | SQLModel + Alembic |
| Auth | JWT (`python-jose`) + bcrypt, cookie `access_token` |
| Agents | CrewAI |
| Vector store | ChromaDB (local, file-based) |
| LLM | OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`) |
| Web search | Tavily (`crewai_tools.TavilySearchTool`) |

---

## What this app does

1. **Auth** — Register / login / logout / me. Login sets an `access_token` httpOnly cookie (not Bearer headers, not localStorage).
2. **Collections** — Create, list, get, delete document collections. Each maps to a ChromaDB collection named `col_{collection_id}`.
3. **Documents** — Upload multiple files (max 10MB each; `.pdf`, `.docx`, `.txt`, `.md`). Upload runs the **Ingestion Crew** synchronously (parse → chunk/embed → tag), then returns document status (`ready` / `failed`).
4. **Query** — Ask questions against a collection once all documents are `ready`.
   - `POST .../query` — hierarchical Query Crew; JSON `{answer, citations, query_id}`.
   - `POST .../query/stream` — sequential streaming crew; SSE (`status` / `token` / `done` / `error`). Prefer this for the chat UI.
5. **History** — Past Q&A (and citations) per collection.

---

## Folder structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, mounts /api, GET /health
│   ├── core/
│   │   ├── config.py              # Pydantic settings from .env
│   │   └── security.py            # bcrypt, JWT, get_current_user (cookie)
│   ├── db/
│   │   └── database.py            # async engine (ssl=require) + session factory
│   ├── models/                    # SQLModel tables
│   │   ├── user.py
│   │   ├── collection.py
│   │   ├── document.py
│   │   └── query_history.py
│   ├── schemas/                   # Request / response DTOs
│   │   ├── auth.py
│   │   ├── collection.py
│   │   ├── document.py
│   │   └── query.py
│   ├── api/
│   │   ├── router.py              # Mounts all routers under /api
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── collections.py
│   │       ├── documents.py
│   │       └── query.py           # Non-stream + SSE stream + history
│   ├── services/
│   │   ├── file_service.py        # Parse PDF / DOCX / TXT / MD
│   │   └── chroma_service.py      # Chroma create / add / search / delete
│   └── crews/
│       ├── tools.py               # FileReaderTool, ChromaStoreTool, ChromaSearchTool
│       ├── ingestion/             # Sequential: parse → chunk+embed → tag
│       │   ├── agents.py
│       │   ├── tasks.py
│       │   └── crew.py
│       └── query/                 # build_query_crew(stream=...)
│           ├── agents.py          # Agent factories (+ Tavily)
│           ├── tasks.py           # Legacy (unused by build_query_crew)
│           └── crew.py            # Hierarchical (non-stream) / sequential (stream)
├── alembic/                       # Migrations
├── alembic.ini
├── pyproject.toml
├── uv.lock
├── chroma_data/                   # Local Chroma persistence (gitignored)
└── uploads/                       # Uploaded files (gitignored)
```

### Crews (high level)

| Crew | Process | When | Role |
| ---- | ------- | ---- | ---- |
| **Ingestion** | Sequential | On document upload | Parse files → chunk & embed into ChromaDB → tag (tags not persisted yet) |
| **Query (non-stream)** | Hierarchical + explicit manager agent | `POST .../query` | Manager routes Retriever / CrossReference / GapAnalyst / Synthesizer; structured `QueryAnswer` |
| **Query (stream)** | Sequential + `stream=True` | `POST .../query/stream` | Same agents in order; SSE forwards Synthesizer tokens only; citations via `__CITATIONS_JSON__` trailer |

---

## API routes

All app routes are under `/api`, except health. Protected routes require a valid **`access_token` httpOnly cookie** (set on login). Do not use `Authorization: Bearer`.

### Root

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/health` | No | Liveness check → `{"status":"ok"}` |

### Auth — `/api/auth`

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/api/auth/register` | No | Create account. Body: `{email, password, name?}`. Returns user. |
| `POST` | `/api/auth/login` | No | Body: `{email, password}`. Sets `access_token` cookie; returns user. |
| `POST` | `/api/auth/logout` | No | Clears `access_token` cookie. |
| `GET` | `/api/auth/me` | Yes | Current user profile. |

### Collections — `/api/collections`

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/api/collections/` | Yes | Create collection. Body: `{name, description?}`. Sets `chroma_collection_id` to `col_{id}`. |
| `GET` | `/api/collections/` | Yes | List collections for the current user. |
| `GET` | `/api/collections/{id}` | Yes | Collection metadata only (no nested documents). |
| `DELETE` | `/api/collections/{id}` | Yes | Delete collection (DB cascade + ChromaDB collection). |

### Documents — `/api/collections/{id}/documents`

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/api/collections/{id}/documents/` | Yes | Multipart upload (`files`). Runs Ingestion Crew synchronously. Returns document list with status / chunk info. |
| `GET` | `/api/collections/{id}/documents` | Yes | List documents in the collection. |
| `DELETE` | `/api/collections/{id}/documents/{doc_id}` | Yes | Delete one document (disk file + Chroma chunks by `doc_id` + DB row). Blocked while `processing`. |

### Query — `/api/collections/{id}`

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `POST` | `/api/collections/{id}/query` | Yes | Non-stream hierarchical crew. Body: `{question}`. Response: `{answer, citations, query_id}`. Blocked if any document is not `ready`. |
| `POST` | `/api/collections/{id}/query/stream` | Yes | SSE stream (`text/event-stream`). Same body. Events: `status` → `token`* → `done` (or `error`). Saves history before `done`. |
| `GET` | `/api/collections/{id}/history` | Yes | Past queries for this collection (`question`, `answer`, `citations`, `created_at`). |

#### Stream events (`/query/stream`)

| Event | Payload | Notes |
| ----- | ------- | ----- |
| `status` | `{"message":"started"}` | Stream began |
| `token` | `{"content":"..."}` | Append fragments (Synthesizer text only) |
| `done` | `{query_id, answer, citations, created_at}` | Authoritative final answer after DB save |
| `error` | `{"message":"..."}` | Failure after the stream started |

Pre-stream failures (auth, missing collection, docs not ready) return normal JSON HTTP errors (`401` / `404` / `400`), not SSE.

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Installation

### Prerequisites

- Python **3.12+**
- [uv](https://github.com/astral-sh/uv)
- A PostgreSQL database (e.g. Neon) with SSL
- OpenAI API key
- Tavily API key (used by query agents)

### Steps

```bash
cd backend

uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv sync
```

Create a `.env` file in `backend/` (there is no `.env.example` in the repo yet):

```env
APP_NAME=DocuCrew
APP_ENV=development
DEBUG=true

DATABASE_URL=postgresql+asyncpg://user:password@host/docucrew?ssl=require

SECRET_KEY=replace-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
SALT_ROUNDS=12

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

CHROMA_PERSIST_DIR=./chroma_data

ALLOWED_ORIGINS=["http://localhost:3000"]

REDIS_URL=redis://localhost:6379

TAVILY_API_KEY=tvly-...
```

Notes:

- `DATABASE_URL` must use the `postgresql+asyncpg://` scheme. The engine always connects with `ssl=require`.
- `REDIS_URL` is declared in config but Redis JWT blacklisting is **not implemented** yet (logout only deletes the cookie).
- `ALLOWED_ORIGINS` must list the frontend origin explicitly (`allow_credentials=True`; `*` is not used).

Run migrations and start the server:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

| URL | Purpose |
| --- | ------- |
| http://localhost:8000 | API |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/health | Health check |

Chroma data is stored under `backend/chroma_data/` (gitignored). Uploaded files live under `backend/uploads/`.
