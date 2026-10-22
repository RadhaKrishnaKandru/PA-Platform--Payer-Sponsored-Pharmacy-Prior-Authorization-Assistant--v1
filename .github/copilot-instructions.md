# PA Platform: Payer-Sponsored Pharmacy Prior Authorization Assistant (v1)

## 1. Problem
Pharmacists discover Prior Authorization (PA) requirements only after claim rejection, causing delays, abandonment, repeated provider calls, incomplete PA submissions, and payer cost. Payers also need early signals of misuse (early refill, duplicate therapy, quantity-limit breaches).

## 2. Objective
Multi-agent AI assistant for network pharmacists. Given an eRx, answer:
1. Does this drug require PA?
2. Why (cited from policy)?
3. What information/documentation is missing?
4. What should be requested from the provider?
5. Any eligibility or utilization concerns?

**Hard rules:** The system NEVER approves/denies a prescription, NEVER recommends medications or alternatives, NEVER predicts approval. It informs and drafts only. Output guardrail must enforce this.

## 3. Users
Pharmacist (primary), Pharmacy Technician, PA team. Owner/funder: payer.

## 4. Scope & Compliance
- v1 uses ONLY synthetic data. No real PHI. State this in README.
- Design HIPAA-aligned: minimum necessary, no PHI in logs, no secrets in code.
- v2 adds: Presidio PHI redaction before LLM calls, audit log, RBAC, human approval, FHIR, Postgres/pgvector, Docker, CI.

## 5. Tech Stack
- Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy + SQLite
- Orchestration: LangGraph (typed shared state, conditional edges)
- LLM: open-source model via Groq (langchain-groq), temperature 0, structured output
- RAG: LangChain, Chroma, local embeddings (HuggingFace bge-small)
- Frontend: React + TypeScript + Vite
- Tests: pytest

## 6. Design Principles
- Deterministic code for lookups/rules (coverage, formulary, fills, quantity limits, early refill, duplicates). LLM only for: eRx extraction, policy interpretation (RAG), gap analysis, provider message drafting.
- Every data source sits behind a function interface in `tools/` (v2 swaps SQLite for FHIR without changing the graph).
- Every policy claim must carry a citation (doc, page, section). If policy not found or retrieval confidence is low: status = `needs_manual_review`. Never guess.
- All node inputs/outputs are Pydantic models. No free-text passing between nodes.
- Type hints everywhere, small pure functions, docstrings, no PHI in logs.

## 7. Graph (LangGraph)
Nodes: extract -> coverage -> policy -> (gaps || utilization) -> guardrail -> provider_msg -> summary

Routing:
- coverage inactive -> END (status=stopped, with reason)
- policy: pa_required=false -> skip gaps/provider_msg, run utilization -> summary
- policy not found/low confidence -> status=needs_manual_review -> summary
- guardrail fail -> regenerate once, then fall back to safe template

Node types:
| Node | Type |
|---|---|
| extract | LLM structured output (drug, NDC, qty, days_supply, prescriber, dx) |
| coverage | code (member eligibility, plan, dates) |
| policy | formulary lookup (code) + RAG retrieval + LLM summary with citations |
| gaps | LLM + rules (required docs vs provided data) |
| utilization | code (early refill, duplicate therapy, qty limit, prior claims/PA history) |
| guardrail | code (regex/validator blocking approve/deny/recommend language) |
| provider_msg | LLM, template-constrained (fax, email, portal note) |
| summary | code (assemble dashboard payload) |

## 8. CaseState
erx, rx, coverage, policy (pa_required, reasons[], citations[]), gaps[] (MissingItem), utilization[] (RiskSignal: type, severity, detail), provider_msg, summary, status (ok|stopped|needs_manual_review), errors[], trace[] (event: node, timestamp, outcome; no PHI).

## 9. RAG
- Ingest: PDF -> section-aware chunks (criteria, documentation, step therapy, quantity limits)
- Metadata: payer, plan, drug, policy_version, effective_date, page
- Retrieve: metadata filter first, then semantic top-k
- Post-check: every citation must reference a retrieved chunk

## 10. Data (synthetic, SQLite)
Tables: members, coverage, formulary (drug, pa_required, qty_limit, age_limit, step_therapy), fills, claims_history, providers. Policies: 3-5 sample PDFs (e.g., GLP-1, biologic, opioid with qty limits). Seed script in `db/seed.py`.

## 11. API
- POST /api/cases (body: eRx JSON) -> runs graph, returns case result
- GET /api/cases/{id}
- GET /api/health
CORS enabled for the Vite dev server.

## 12. Frontend
Pages: NewCase (eRx form/JSON upload), CaseResult (dashboard). Cards: Coverage, PA required + reason, Missing info, Risk signals, Provider message (copy buttons), Citations.

## 13. Eval
`tests/eval/golden_cases.json`: 15-20 synthetic cases including inactive coverage, early refill, duplicate therapy, missing policy, no-PA drug, quantity-limit breach. `run_eval.py` reports PA-detection accuracy, gap precision/recall, citation validity, guardrail pass rate.

## 14. Folder Structure
pa-platform/
├── README.md
├── .github/copilot-instructions.md
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/ (routes_cases.py, schemas.py)
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── builder.py
│   │   │   └── nodes/ (extract, coverage, policy, gaps, utilization, guardrail, provider_msg, summary).py
│   │   ├── tools/ (coverage, formulary, fills, providers).py
│   │   ├── rag/ (ingest.py, retriever.py, prompts.py)
│   │   ├── llm/client.py
│   │   ├── db/ (models.py, session.py, seed.py)
│   │   └── core/logging.py
│   ├── data/ (policies/, erx_samples/, chroma/ [gitignored])
│   └── tests/ (test_tools.py, test_graph.py, eval/golden_cases.json, eval/run_eval.py)
└── frontend/
    ├── package.json, vite.config.ts
    └── src/
        ├── main.tsx, App.tsx
        ├── api/client.ts
        ├── pages/ (NewCase.tsx, CaseResult.tsx)
        ├── components/ (CoverageCard, PACard, GapsList, RiskSignals, ProviderMessage, CitationList).tsx
        └── types/case.ts

## 15. Build Order
1 setup -> 2 data/seed -> 3 tools + tests -> 4 state + graph with stub nodes -> 5 RAG -> 6 LLM nodes + guardrail -> 7 eval -> 8 API + React UI + README.

## 16. v1 Non-Goals
Auth, PHI redaction, FHIR, audit immutability, human-approval interrupts, Docker/CI. (All v2.)