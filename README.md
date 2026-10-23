# PA Platform: Pharmacy Prior Authorization Assistant

A multi-agent AI assistant that helps network pharmacists identify Prior Authorization (PA) requirements, understand why, find documentation gaps, and draft provider outreach, before a claim is rejected.

> **Synthetic data only.** This is a personal learning project. It contains no real PHI and is **not** a certified HIPAA-compliant system. It is designed HIPAA-aligned (minimum necessary, no PHI in logs, no secrets in code).

**Status:** v1 in development. The LangGraph workflow, tracing, guardrails, and LLM factory are built and tested. The data layer (Postgres, Mongo), RAG ingestion, case API, evaluation harness, and React UI are in progress.

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
| Document DB | MongoDB: cases, provider messages, trace events |
| Vector store | Chroma (pgvector planned for v2) |
| Orchestration | LangGraph |
| LLM | Open-source models via Groq (LangChain): a fast model and a stronger model, configurable |
| Embeddings | HuggingFace bge-small (local) |
| Frontend | React, TypeScript, Vite (planned) |
| Infra / Testing | Docker Compose, pytest |

## Project Structure

```text
pa-platform/
├── docker-compose.yml        # postgres + mongo
├── backend/
│   ├── app/
│   │   ├── api/              # routes, schemas
│   │   ├── graph/            # state, builder, nodes/
│   │   ├── tools/            # coverage, formulary, fills, providers
│   │   ├── rag/              # ingest, retriever, prompts
│   │   ├── llm/              # Groq client factory
│   │   └── db/               # postgres, mongo, models, seed (planned)
│   ├── data/                 # policies/, erx_samples/
│   └── tests/                # unit tests + eval/
└── frontend/                 # React + Vite UI (planned)
```

## Getting Started

### Prerequisites
Python 3.11+ is required for the backend (developed and tested on Python 3.14). Docker is needed to start the local PostgreSQL and MongoDB services. A free Groq API key is needed for the LLM nodes. Node.js is needed when the frontend is added.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
```
`backend/.env.example` contains placeholders only. Copy it to `backend/.env` and fill in your own values. **Replace every placeholder before running `docker compose up`**, because the database starts with whatever password is in `backend/.env`. Keep `backend/.env` private; it is ignored by Git and must never be committed. The model name settings are optional (defaults are built in).

```bash
cd ..
docker compose --env-file backend/.env up -d
cd backend
uvicorn app.main:app --reload
```

The local MongoDB service has no authentication and is bound to `127.0.0.1` only. Enabling auth is a v2 hardening item.

The initial API exposes `GET /api/health` and interactive docs at http://localhost:8000/docs. The health route confirms that the API process is responding; database dependency checks will be added with persistence.

### Frontend
The frontend scaffold will be added in a later phase.

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

## Disclaimer
For educational purposes only. Not medical, legal, or coverage advice. Do not use with real patient data.

## License
MIT