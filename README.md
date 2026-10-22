# PA Platform: Pharmacy Prior Authorization Assistant

A multi-agent AI assistant that helps network pharmacists identify Prior Authorization (PA) requirements, understand why, find documentation gaps, and draft provider outreach, before a claim is rejected.

> **Synthetic data only.** This is a personal learning project. It contains no real PHI and is **not** a certified HIPAA-compliant system. It is designed HIPAA-aligned (minimum necessary, no PHI in logs, no secrets in code).

## Problem
Pharmacists often learn a drug needs PA only after claim rejection, causing treatment delays, prescription abandonment, repeated provider calls, and incomplete PA submissions. Payers also need early signals of misuse (early refills, duplicate therapy, quantity-limit breaches).

## What It Answers
1. Does this drug require PA?
2. Why? (cited from payer policy)
3. What information is missing?
4. What should be requested from the provider?
5. Are there eligibility or utilization concerns?

**Guardrails:** The system never approves or denies a prescription, never recommends medications, and never predicts approval. It informs and drafts only.

## Architecture

React UI -> FastAPI -> LangGraph workflow
|
extract -> coverage -> policy (RAG) -> gaps || utilization
-> guardrail -> provider message -> summary
|
Postgres (rules/data) | MongoDB (cases, traces) | Chroma (policy chunks) | Groq LLM


- **Deterministic code** handles coverage, formulary, fills, quantity limits, and early refill checks.
- **LLM** is used only for eRx extraction, policy interpretation (RAG with citations), gap analysis, and provider message drafting.
- **Safe failure:** if the policy is missing or retrieval confidence is low, the case is flagged `needs_manual_review` instead of guessing.

## Tech Stack
| Layer | Tech |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Relational DB | PostgreSQL (SQLAlchemy): coverage, formulary, fills, claims, providers |
| Document DB | MongoDB: cases, provider messages, trace events |
| Vector store | Chroma (pgvector planned for v2) |
| Orchestration | LangGraph |
| LLM | Open-source model via Groq (LangChain) |
| Embeddings | HuggingFace bge-small (local) |
| Frontend | React, TypeScript, Vite |
| Infra / Testing | Docker Compose, pytest |

## Project Structure

pa-platform/
├── docker-compose.yml # postgres + mongo
├── backend/
│ ├── app/
│ │ ├── api/ # routes, schemas
│ │ ├── graph/ # state, builder, nodes/
│ │ ├── tools/ # coverage, formulary, fills, providers
│ │ ├── rag/ # ingest, retriever, prompts
│ │ ├── llm/ # Groq client
│ │ ├── db/ # postgres, mongo, models, seed
│ │ └── core/ # logging
│ ├── data/ # policies/, erx_samples/
│ └── tests/ # unit tests + eval/
└── frontend/ # React + Vite UI


## Getting Started

### Prerequisites
Python 3.11+ is required for the backend. Docker is needed to start the local PostgreSQL and MongoDB services. A Groq API key and Node.js will be needed when the LLM and frontend are implemented.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # keep real credentials and local settings in this ignored file
cd ..
docker compose --env-file backend/.env up -d
cd backend
uvicorn app.main:app --reload
```
`backend/.env.example` contains only local-development defaults and placeholders. Keep your actual `backend/.env` private; it is ignored by Git and must not be committed. Replace the example database password before using the services outside a local development environment.

The initial API exposes `GET /api/health` and interactive docs at http://localhost:8000/docs. The health route confirms that the API process is responding; database dependency checks will be added with persistence.

### Frontend
The frontend scaffold will be added in a later phase.

## Example Output

Medication: Ozempic
Coverage: Active
Prior Authorization: Required
Reason: Policy requires clinical review (Policy X, p.4, Criteria)
Missing: 1. Provider clinical notes 2. Supporting lab results
Utilization: No concerns identified
Recommended action: Contact prescriber and request supporting documentation
Provider message: Generated (fax / email / portal note)


## Evaluation
```bash
cd backend && python -m tests.eval.run_eval
```
Runs 15-20 synthetic golden cases (inactive coverage, early refill, duplicate therapy, missing policy, no-PA drug, quantity-limit breach). Reports PA-detection accuracy, gap precision/recall, citation validity, and guardrail pass rate.

## Roadmap
- **v1 (this version):** core workflow, RAG with citations, FastAPI + React UI, Postgres + Mongo + Chroma, eval harness
- **v2 (planned):** Presidio PHI redaction before LLM calls, immutable audit log (Mongo trace), RBAC, human-approval step, FHIR sandbox integration, pgvector replaces Chroma, CI, threat model mapped to HIPAA Security Rule safeguards, local LLM option

## Disclaimer
For educational purposes only. Not medical, legal, or coverage advice. Do not use with real patient data.

## License
MIT
