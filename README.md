# PA Platform: Pharmacy Prior Authorization Assistant

A multi-agent AI assistant that helps network pharmacists identify Prior Authorization (PA) requirements, understand why, find documentation gaps, and draft provider outreach, before a claim is rejected.

> **Synthetic data only.** This is a personal learning project. It contains no real PHI and is **not** a certified HIPAA-compliant system. It is designed HIPAA-aligned (minimum necessary, no PHI in logs, no secrets in code).

**Status:** v1 in development. The LangGraph workflow, tracing, guardrails, LLM factory, PostgreSQL data layer with real tools, and local policy RAG are built and tested. MongoDB persistence, the case API, evaluation harness, and React UI are in progress.

## Problem
Pharmacists often learn a drug needs PA only after claim rejection, causing treatment delays, prescription abandonment, repeated provider calls, and incomplete PA submissions. Payers also need early signals of misuse (early refills, duplicate therapy, quantity-limit breaches).

## What It Answers
1. Does this drug require PA?
2. Why? (cited from payer policy)
3. What information is missing?
4. What should be requested from the provider?
5. Are there eligibility or utilization concerns?

**Guardrails:** The system never approves or denies a prescription, never recommends medications, and never predicts approval. It informs and drafts only. An output guardrail enforces this and keeps provider messages in draft status.

## Architecture

```text
React UI -> FastAPI -> LangGraph workflow

extract -> coverage -> policy (RAG) -> gaps || utilization
        -> provider message -> guardrail -> summary

Postgres (rules/data) | MongoDB (cases, traces) | Chroma (policy chunks) | Groq LLM
```

- **Deterministic code** handles coverage, formulary, fills, quantity limits, and early refill checks.
- **LLM** is used only for eRx extraction (when needed), policy interpretation (RAG with citations), gap analysis, and provider message drafting.
- **Parallel checks:** documentation gaps and utilization review run in parallel when PA is required.
- **Safe failure:** if the policy is missing or retrieval confidence is low, the case is flagged `needs_manual_review` instead of guessing.
- **Tracing:** every node records outcome and duration (no case data, no PHI).

## Tech Stack
| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Relational DB | PostgreSQL (SQLAlchemy): coverage, formulary, fills, claims, providers |
| Document DB | MongoDB (hosted, e.g. MongoDB Atlas free tier; persistence is being added) |
| Vector store | Chroma (pgvector planned for v2) |
| Orchestration | LangGraph |
| LLM | Open-source models via Groq (LangChain): a fast model and a stronger model, configurable |
| Embeddings | HuggingFace bge-small (local) |
| Frontend | React, TypeScript, Vite (planned) |
| Testing | pytest |

## Project Structure

```text
pa-platform/
├── backend/
│   ├── app/
│   │   ├── api/              # routes, schemas
│   │   ├── graph/            # state, builder, nodes/
│   │   ├── tools/            # coverage, formulary, fills, providers
│   │   ├── rag/              # embeddings, ingest, retriever
│   │   ├── llm/              # Groq client factory
│   │   └── db/               # postgres, models, seed (mongo planned)
│   ├── data/                 # policies/, erx_samples/
│   └── tests/                # unit tests + eval/
└── frontend/                 # React + Vite UI (planned)
```

## Getting Started

### Prerequisites
Python 3.11+ (tested on Python 3.14), PostgreSQL 14+ installed locally, and a free Groq API key are required. Node.js is needed when the frontend is added. A hosted MongoDB (Atlas free tier) will be needed when MongoDB persistence is added.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
```
`backend/.env.example` contains placeholders only. Fill in your own values in `backend/.env`. **Never commit `backend/.env`. Only synthetic data may be stored, including in any hosted database.**

### Local PostgreSQL
Install PostgreSQL (for example, on Ubuntu):
```bash
sudo apt install postgresql
```

Create a database user and database with `psql` (replace the example names and password with your own):
```sql
CREATE USER YOUR_USER WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE YOUR_DATABASE OWNER YOUR_USER;
```

Set `POSTGRES_URL` in `backend/.env` using the SQLAlchemy psycopg3 form below. The `+psycopg` driver prefix is required; the project uses psycopg 3:
```dotenv
POSTGRES_URL="postgresql+psycopg://USER:PASSWORD@localhost:5432/DBNAME"
```

### Seed the synthetic data
From `backend/`:
```bash
python -m app.db.seed
```

### Build the policy index
From `backend/`:
```bash
python -m app.rag.ingest
```
The first run downloads the local embedding model; no Hugging Face key is needed. The policy PDFs are synthetic, and `backend/data/chroma/` is generated by ingestion and ignored by Git.

### Run tests
Run from `backend/`:
```bash
python -m pytest
```
PostgreSQL integration tests run when `POSTGRES_URL` is set in `backend/.env` or exported in the shell. An exported shell variable overrides the `.env` value; unset stale shell values when you want to use the `.env` setting. To export the connection string for one run:
```bash
export POSTGRES_URL="postgresql+psycopg://USER:PASSWORD@localhost:5432/DBNAME"
python -m pytest
unset POSTGRES_URL
```

### Run the API
From `backend/`:
```bash
uvicorn app.main:app --reload
```
The API exposes `GET /api/health` and interactive docs at http://localhost:8000/docs.

## Example Output

```text
Medication: Ozempic
Coverage: Active
Prior Authorization: Required
Reason: Policy requires clinical review (Policy X, p.4, Criteria)
Missing: 1. Provider clinical notes  2. Supporting lab results
Utilization: No concerns identified
Recommended action: Contact prescriber and request supporting documentation
Provider message: Generated (fax / email / portal note)
```

## Evaluation
```bash
cd backend && python -m pytest
```
The current automated tests cover the API health endpoint, local Vite CORS behavior, and the graph routing scenarios (inactive coverage, PA required, PA not required, policy not found, parallel node failures, and tracing) with the LLM mocked. The synthetic golden-case evaluation harness and its accuracy metrics are planned but are not implemented yet.

## Roadmap
- **v1 (in development):** core workflow, RAG with citations, FastAPI + React UI, Postgres + Mongo + Chroma, eval harness
- **v2 (planned):** Presidio PHI redaction before LLM calls, immutable audit log (Mongo trace), RBAC, human-approval step, FHIR sandbox integration, pgvector replaces Chroma, MongoDB auth, CI, threat model mapped to HIPAA Security Rule safeguards, local LLM option

Hosted-database hardening: IP allow-listing, strong credentials, private networking, and encryption settings.

## Disclaimer
For educational purposes only. Not medical, legal, or coverage advice. Do not use with real patient data.

## License
MIT