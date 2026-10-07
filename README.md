# SecureRAG Demo — Multi-Modal RAG with Retrieval-Layer Access Control

A portfolio/demo project that **proves** access control is enforced at the
retrieval layer inside PostgreSQL — not filtered in application code after
the fact.

## Architecture at a Glance

```
 ┌─────────┐  JWT  ┌─────────────────┐ SET LOCAL  ┌────────────┐
 │Browser  │──────▶│  FastAPI        │ app.*      │ PostgreSQL │
 │frontend │       │  (routes)       │──────────▶│  + pgvector │
 └─────────┘       │                 │            │  + RLS     │
                   │                 │            │            │
                   │  embed (local)  │ 1 SQL query│ chunks    │
                   │  search+ACL     │◀═══════════│ employee_  │
                   │  (vector<=>+ACL)│  WHERE     │  records   │
                   │                 │  current_  │            │
                   │  LLM generate   │  setting() │            │
                   │  verify claims  │            │            │
                   └─────────────────┘            └────────────┘
```

### The Security Guarantee

Two **independent** enforcement layers, both inside PostgreSQL:

| Layer | Mechanism | What it protects against |
|-------|-----------|--------------------------|
| **1. Fused SQL** | `WHERE … current_setting('app.user_id') = ANY(allowed_principals) …` in the vector-search query | The query **never returns** unauthorized rows — no "fetch top-K then discard in Python" anti-pattern |
| **2. RLS policies** | `CREATE POLICY … USING (… current_setting(…) …)` on `chunks` and `employee_records` | Even if a future query forgets the WHERE clause, RLS still blocks unauthorized reads |

Per-request session variables are stamped via `SET LOCAL` /
`set_config(…, is_local=true)` inside a transaction, derived from the
JWT claims — never a superuser connection filtered afterward.

> **Known tradeoff:** pgvector + a WHERE clause is filtered during Postgres'
> query planning, not as true filter-integrated HNSW graph traversal the way
> Qdrant/Weaviate do it. Fine at demo scale (hundreds to low thousands of
> chunks). Production answer: Qdrant/Weavide for filtered-HNSW at scale; this
> demo trades that for one database and one enforcement mechanism covering
> both vector and structured access.

## Stack

| Layer | Technology |
|-------|-----------|
| API | Python 3.12, FastAPI, SQLAlchemy |
| Database | PostgreSQL 16 + pgvector (HNSW index, RLS) |
| Auth | JWT (python-jose) — `user_id`, `role`, `tenant_id` claims |
| PDF extraction | PyMuPDF (`pymupdf`) |
| OCR | pytesseract + Pillow |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, 384-dim) |
| LLM | Gemini 2.0 Flash via OpenAI-compatible endpoint |
| Frontend | Single vanilla HTML/CSS/JS file |

## Prerequisites

1. **PostgreSQL 16** with the `pgvector` extension
2. **Python 3.12**
3. **Tesseract OCR engine** (for scanned-image processing)
4. **Gemini API key** (for answer generation) — get one at https://aistudio.google.com

### Installing pgvector on PostgreSQL

**Windows** (pre-built binaries):
```powershell
# Download from https://github.com/portalcorp/pgvector_compiled/releases
# Copy vector.dll to <pgsql>/lib/
# Copy vector*.sql, vector.control to <pgsql>/share/extension/
psql -U postgres -d <your_db> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**macOS** (Homebrew):
```bash
brew install pgvector
```

**Linux**:
```bash
apt install postgresql-pgvector
# or build from source: https://github.com/pgvector/pgvector
```

### Installing Tesseract OCR

- **Windows**: `winget install UB-Mannheim.TesseractOCR`
- **macOS**: `brew install tesseract`
- **Linux**: `apt install tesseract-ocr`

## Installation

```bash
git clone <this-repo>
cd secure-rag-demo
pip install -r requirements.txt
```

## Setup

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   DATABASE_URL  — your PostgreSQL connection string
#   GEMINI_API_KEY — your Gemini API key
#   TESSERACT_CMD — path to tesseract.exe (Windows only; leave blank on macOS/Linux)
```

### 2. Initialize the database

```bash
python scripts/init_db.py
```

This runs the three migration files in order:
1. `001_extensions.sql` — `CREATE EXTENSION vector`
2. `002_schema.sql` — tables + HNSW index
3. `003_rls_policies.sql` — two RLS policies on each table

### 3. Seed demo data

```bash
python scripts/seed.py
```

This:
- Generates `seed_data/hr_policy.pdf` (native text, HR-only)
- Generates `seed_data/finance_scan.png` (scanned image, finance-only, requires OCR)
- Inserts 10 `employee_records` rows (5 salary = finance-only, 5 reviews = HR-only)
- Runs the full ingestion pipeline (extract → chunk → embed → insert)
- Creates chunks with per-document `allowed_principals`

### 4. Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Run the test suite

```bash
pytest tests/ -v
```

## Demo Walkthrough

**Question:** "What is John Smith's salary and performance review status?"

### As Alice (HR manager)

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice"}'
# → { "access_token": "...", "token_type": "bearer" }
# Save the token, then query:
curl -X POST http://localhost:8000/query \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is John Smith'"'"'s salary and performance review status?"}'
```

Alice sees:
- **Performance review:** "John Smith's performance review status is Exceeds Expectations" — with citations
- **Salary:** "not found in your accessible documents" — because finance-only chunks were never returned by the search

### As Carol (admin)

Same question, same endpoint — but login as `carol`:

Carol sees:
- **Salary:** "John Smith's annual salary is $85,000" — with finance citation
- **Performance review:** "John Smith's performance review status is Exceeds Expectations" — with HR citation

### Using the frontend

Open `frontend/index.html` in a browser, select a user from the dropdown,
and ask the suggested question.

## Demo Users

| Username | user_id | role | tenant_id | Can see |
|----------|---------|------|-----------|---------|
| alice | 1 | hr_manager | 1 | HR docs + HR records |
| bob | 2 | finance_manager | 1 | Finance docs + Finance records |
| carol | 3 | admin | 1 | All documents |

## API Reference

### `GET /health`
Returns `{"status": "ok"}`.

### `POST /auth/login`
```jsonc
// Request
{ "username": "alice" }   // "alice" | "bob" | "carol"

// Response
{ "access_token": "<jwt>", "token_type": "bearer" }
```

### `POST /ingest/` *(admin only)*
Accepts a multipart file upload (PDF, image, or CSV).
```
curl -X POST http://localhost:8000/ingest/ \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@document.pdf"
```

### `POST /query/` *(authenticated)*
```jsonc
// Request
{ "question": "What is John Smith's salary?" }

// Response
{
  "answer": "John Smith's performance review status is Exceeds Expectations [chunk_3]. Salary info is not found in your accessible documents.",
  "citations": [
    {
      "chunk_id": 3,
      "source_type": "db",
      "exact_locator": {"source":"db","table":"employee_records","row_id":2,"field_name":"performance_review"},
      "snippet": "John Smith's performance review..."
    }
  ]
}
```

## How ACL Enforcement Works in the Code

1. **JWT → session variables** (`app/auth/dependencies.py` + `app/db/session.py`):
   The `get_current_user` dependency decodes the Bearer token. The `get_db`
   dependency opens a transaction and runs:
   ```sql
   SELECT set_config('app.user_id',    '1',     true);   -- is_local = true
   SELECT set_config('app.user_role',  'hr_manager', true);
   SELECT set_config('app.tenant_id',  '1',     true);
   ```

2. **Fused vector + ACL query** (`app/retrieval/vector_search.py`):
   ```sql
   SELECT chunk_id, raw_text, exact_locator, source_doc_id, source_type,
          embedding <=> CAST(%(query_embedding)s AS vector(384)) AS distance
   FROM chunks
   WHERE tenant_id = current_setting('app.tenant_id')::int
     AND (current_setting('app.user_id') = ANY(allowed_principals)
          OR current_setting('app.user_role') = ANY(allowed_principals))
   ORDER BY distance
   LIMIT 10;
   ```
   The HNSW index (`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`)
   serves as the ANN index; the WHERE clause filters during Postgres query
   planning. **No Python-side filtering of unauthorized rows.**

3. **RLS backup** (`app/db/migrations/003_rls_policies.sql`):
   `ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;` plus two `USING` policies
   that reference the same `current_setting()` variables. If any future query
   forgets the WHERE clause, RLS still blocks unauthorized reads.

4. **Claim verification** (`app/generation/verifier.py`):
   After the LLM generates an answer, a second LLM call checks each cited
   chunk — unsupported claims are stripped.

## Project Structure

```
.
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app/
│   ├── main.py                          # FastAPI app
│   ├── config.py                        # dotenv → settings
│   ├── auth/
│   │   ├── jwt_handler.py              # encode/decode JWT
│   │   └── dependencies.py             # FastAPI get_current_user + role checker
│   ├── db/
│   │   ├── models.py                   # SQLAlchemy models (Chunk, EmployeeRecord)
│   │   ├── session.py                  # engine, SessionLocal, set_session_user
│   │   └── migrations/
│   │       ├── 001_extensions.sql      # CREATE EXTENSION vector
│   │       ├── 002_schema.sql          # tables + HNSW index
│   │       └── 003_rls_policies.sql    # RLS policies (2nd enforcement layer)
│   ├── ingestion/
│   │   ├── pdf_extractor.py            # PyMuPDF — text + page/bbox
│   │   ├── ocr_extractor.py            # pytesseract — text + confidence
│   │   ├── db_templater.py             # row → natural-language sentence
│   │   ├── chunker.py                  # semantic chunking, 15% overlap
│   │   ├── embedder.py                 # sentence-transformers (local)
│   │   └── pipeline.py                 # orchestrates extract→chunk→embed→insert
│   ├── retrieval/
│   │   ├── acl_filter.py               # ACL WHERE-clause predicate (current_setting)
│   │   └── vector_search.py            # single fused vector+ACL SQL query
│   ├── generation/
│   │   ├── llm_client.py               # provider-agnostic OpenAI-compatible wrapper
│   │   ├── prompt_templates.py         # citation-constrained system prompts
│   │   └── verifier.py                 # post-generation claim verification
│   └── routes/
│       ├── health_routes.py            # GET /health
│       ├── auth_routes.py              # POST /auth/login
│       ├── ingest_routes.py            # POST /ingest/ (admin)
│       └── query_routes.py             # POST /query/
├── frontend/
│   └── index.html                      # single vanilla HTML/CSS/JS page
├── scripts/
│   ├── init_db.py                      # migration runner
│   ├── seed.py                         # demo data + document ingestion
│   └── seed_data/
│       ├── hr_policy.pdf               # native text, HR-only
│       └── finance_scan.png            # scanned image, Finance-only, OCR
└── tests/
    └── test_acl_enforcement.py         # alice can't see bob's scope (required test)
```
