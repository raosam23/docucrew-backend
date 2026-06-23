<div align="center">

# DocuCrew — Backend

**Multi-document intelligence platform powered by CrewAI & RAG.**

Upload documents, ask questions, and get cited answers synthesized across your entire corpus by a crew of specialized AI agents.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-FF5A50?style=for-the-badge&logo=robotframework&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-4B32C3?style=for-the-badge&logo=databricks&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white)

</div>

---

## What it does

A user uploads a set of documents (PDF, DOCX, TXT, MD). The **Ingestion Crew** parses, chunks, and embeds them into ChromaDB. On every question, a hierarchical **Query Crew** — managed by an LLM — retrieves the most relevant chunks, cross-references them, detects gaps, and synthesizes a clear, **cited** answer. The last 5 Q&A pairs are fed back as context, so the chat remembers.

---

## Setup & Installation

```bash
# 1. Clone & enter the backend
cd backend

# 2. Create the virtual environment and install deps (uv)
uv venv
source .venv/bin/activate
uv sync

# 3. Configure environment — copy and fill in your keys
cp .env.example .env        # add OPENAI_API_KEY, DATABASE_URL, SECRET_KEY, ...

# 4. Run migrations
uv run alembic upgrade head

# 5. Start the server
uv run uvicorn app.main:app --reload
```

> API → `http://localhost:8000` · Swagger docs → `http://localhost:8000/docs`

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   ├── core/                   # config (Pydantic settings) + security (JWT, bcrypt)
│   ├── db/                     # async engine + session factory
│   ├── models/                 # SQLModel ORM tables (user, collection, document, query_history)
│   ├── schemas/                # Pydantic request/response DTOs
│   ├── api/
│   │   ├── router.py           # mounts all sub-routers under /api
│   │   └── routes/             # auth · collections · documents · query
│   ├── services/               # file parsing · chroma_service · collection logic
│   └── crews/
│       ├── tools.py            # custom CrewAI tools (FileReader, ChromaStore, ChromaSearch)
│       ├── ingestion/          # Sequential crew: parse → chunk+embed → tag
│       └── query/              # Hierarchical crew: retrieve → cross-ref → synthesize → gap
├── alembic/                    # migrations
└── pyproject.toml
```

---

## API Routes

All routes are mounted under `/api`. Auth = requires `Authorization: Bearer <jwt>`.

### Auth — `/api/auth`

| Method | Path        | Auth | Description                   |
| :----: | ----------- | :--: | ----------------------------- |
| `POST` | `/register` |  No  | Register, returns user object |
| `POST` | `/login`    |  No  | Authenticate, returns JWT     |
| `GET`  | `/me`       | Yes  | Current user profile          |

### Collections — `/api/collections`

| Method   | Path     | Auth | Description                                          |
| :------: | -------- | :--: | ---------------------------------------------------- |
| `POST`   | `/`      | Yes  | Create a new collection                              |
| `GET`    | `/`      | Yes  | List all collections for the current user            |
| `GET`    | `/{id}`  | Yes  | Get a single collection with its documents           |
| `DELETE` | `/{id}`  | Yes  | Delete collection (cascades docs + ChromaDB)         |

### Documents — `/api/collections/{id}/documents`

| Method   | Path             | Auth | Description                                                       |
| :------: | ---------------- | :--: | ---------------------------------------------------------------- |
| `POST`   | `/`              | Yes  | Upload files (multipart). Triggers the Ingestion Crew synchronously |
| `GET`    | `/`              | Yes  | List documents in a collection                                   |
| `DELETE` | `/{document_id}` | Yes  | Delete a single document (removes its chunks from ChromaDB too)  |

### Query — `/api/collections/{id}`

| Method | Path       | Auth | Description                                                      |
| :----: | ---------- | :--: | --------------------------------------------------------------- |
| `POST` | `/query`   | Yes  | Run the Query Crew. Returns `{answer, citations, query_id}`     |
| `GET`  | `/history` | Yes  | Past queries and answers for this collection                    |

---

<div align="center">
<sub>Built with FastAPI · CrewAI · ChromaDB · PostgreSQL</sub>
</div>
