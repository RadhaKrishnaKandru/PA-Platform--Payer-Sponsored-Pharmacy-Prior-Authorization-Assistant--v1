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

**Hard rules:** The system NEVER approves/denies a prescription, NEVER recommends medications or alternatives, NEVER predicts approval. It informs and drafts only. The output guardrail must enforce this.

## 3. Users
Pharmacist (primary), Pharmacy Technician, PA team. Owner/funder: payer.

## 4. Scope & Compliance
- v1 uses ONLY synthetic data. No real PHI. State this in README.
- Design HIPAA-aligned: minimum necessary, no PHI in logs, no secrets in code.
- v2 adds: Presidio PHI redaction before LLM calls, audit log, RBAC, human approval, FHIR, Postgres/pgvector, MongoDB auth, CI.

## 5. Tech Stack
- Backend: Python 3.11+ (tested on 3.14), FastAPI, Pydantic v2
- Relational DB: PostgreSQL (SQLAlchemy + psycopg): members, coverage, formulary, fills, claims_history, providers
- Document DB: MongoDB (hosted, e.g. Atlas free tier)
- Vector store: Chroma (v1; pgvector planned for v2)
- Orchestration: LangGraph (typed shared state, conditional edges)
- LLM: open-source models via Groq (langchain-groq), temperature 0, structured output
- Embeddings: local HuggingFace bge-small
- Frontend: React + TypeScript + Vite
- Tests: pytest

## 6. Design Principles
- Deterministic code for lookups/rules (coverage, formulary, fills, quantity limits, early refill, duplicates). LLM only for: eRx extraction (when needed), policy interpretation (RAG), gap analysis, provider message drafting.
- Every data source sits behind a function interface in `tools/` (v2 swaps in FHIR without changing the graph).
- Every policy claim must carry a citation (doc, page, section). If policy not found or retrieval confidence is low: status = `needs_manual_review`. Never guess.
- All node inputs/outputs are Pydantic models. No free-text passing between nodes.
- LLM models come from settings: `FAST_MODEL` (default openai/gpt-oss-20b) for extract and gaps, `STRONG_MODEL` (default openai/gpt-oss-120b) for policy and provider_msg. Always use `get_llm()` from `app/llm/client.py`. Groq free tier is rate limited (about 8k tokens per minute), so keep prompts short and send at most 3 retrieved chunks.
- Type hints everywhere, small pure functions, docstrings, no PHI in logs.

## 7. Graph (LangGraph)
Flow: extract -> coverage -> policy -> (gaps || utilization) -> provider_msg -> guardrail -> summary

Routing (see `graph/builder.py`):
- coverage not active -> summary (status=stopped, with reason)
- policy found and pa_required=true -> gaps and utilization run in parallel, join, then provider_msg -> guardrail
- policy found and pa_required=false -> utilization -> summary (no provider_msg)
- policy not found / low confidence / conflict -> utilization -> summary with status=needs_manual_review
- guardrail fail -> regenerate provider_msg using `guardrail_violations` (max 2 attempts), then summary with needs_manual_review

Node types:
| Node | Type |
|---|---|
| extract | code first; LLM only when fields are missing or input is free text |
| coverage | code (member eligibility, plan, dates) |
| policy | formulary lookup (code) + RAG retrieval + LLM summary with citations |
| gaps | LLM + rules (required docs vs provided data) |
| utilization | code (early refill, duplicate therapy, qty limit, prior claims/PA history) |
| provider_msg | LLM, template-constrained (fax, email, portal note) |
| guardrail | code (blocks approve/deny/recommend/predict language, enforces draft status) |
| summary | code (assemble dashboard payload) |

## 8. CaseState
Fields: erx, rx, coverage, policy (status, pa_required, reasons[], citations[]), gaps[], utilization[], provider_msg, summary, status, guardrail_passed, guardrail_attempts, guardrail_violations[], errors[], trace[].
- `status` uses a reducer (`worst_status`: stopped > needs_manual_review > ok) so parallel nodes can both write it.
- `errors` and `trace` use `operator.add` reducers: nodes return only NEW items, never the full list.
- Every node is wrapped with `@traced("name")` from `graph/nodes/_trace.py` (no PHI in trace events: only node, time, outcome, duration, error category).

## 9. RAG
- Ingest: PDF -> section-aware chunks (criteria, documentation, step therapy, quantity limits)
- Metadata: payer, plan, drug, policy_version, effective_date, page
- Retrieve: metadata filter first, then semantic top-k via `retrieve_policy_chunks(drug=, ndc=, plan_id=)` in `rag/retriever.py` (currently a stub returning [])
- Post-check: every citation must reference a retrieved chunk

## 10. Data (synthetic only)
- PostgreSQL tables: members, coverage, formulary (drug, pa_required, qty_limit, age_limit, step_therapy), fills, claims_history, providers. Seeded by `db/seed.py`.
- MongoDB collections: `cases` (eRx + final CaseState + status), `provider_messages`, `trace` (node, timestamp, outcome; no PHI).
- Chroma: policy chunks with metadata (payer, plan, drug, policy_version, effective_date, page).
- Policies: 3-5 sample PDFs (e.g., GLP-1, biologic, opioid with qty limits).
- Deterministic tools read Postgres only. Graph results and traces are written to Mongo.

## 11. API
- POST /api/cases: body eRx JSON, runs graph, saves to Mongo, returns result
- GET /api/cases/{id}: reads from Mongo
- GET /api/health: checks Postgres, Mongo, Chroma
CORS is limited to the Vite dev origins (localhost:5173). Config via `backend/.env` (see `backend/.env.example`).

## 12. Frontend
Pages: NewCase (eRx form/JSON upload), CaseResult (dashboard). Cards: Coverage, PA required + reason, Missing info, Risk signals, Provider message (copy buttons), Citations.

## 13. Eval
`tests/eval/golden_cases.json`: 15-20 synthetic cases including inactive coverage, early refill, duplicate therapy, missing policy, no-PA drug, quantity-limit breach. `run_eval.py` reports PA-detection accuracy, gap precision/recall, citation validity, guardrail pass rate.

## 14. Folder Structure

```
pa-platform/
├── README.md
├── .gitignore
├── .github/
│   └── copilot-instructions.md
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── .env.example                # placeholders only; copy to backend/.env (never commit .env)
│   ├── app/
│   │   ├── main.py                 # FastAPI entry, CORS
│   │   ├── config.py               # settings from env
│   │   ├── api/
│   │   │   ├── routes_health.py    # GET /api/health
│   │   │   ├── routes_cases.py     # POST /api/cases, GET /api/cases/{id}
│   │   │   └── schemas.py
│   │   ├── graph/
│   │   │   ├── state.py            # CaseState + reducers
│   │   │   ├── builder.py          # LangGraph wiring + routing
│   │   │   └── nodes/
│   │   │       ├── _trace.py       # @traced decorator
│   │   │       ├── extract.py
│   │   │       ├── coverage.py
│   │   │       ├── policy.py
│   │   │       ├── gaps.py
│   │   │       ├── utilization.py
│   │   │       ├── provider_msg.py
│   │   │       ├── guardrail.py
│   │   │       └── summary.py
│   │   ├── tools/                  # deterministic data access (Postgres)
│   │   │   ├── coverage.py
│   │   │   ├── formulary.py
│   │   │   ├── fills.py
│   │   │   └── providers.py
│   │   ├── rag/
│   │   │   ├── embeddings.py
│   │   │   ├── ingest.py
│   │   │   ├── retriever.py
│   │   ├── llm/
│   │   │   └── client.py           # get_llm(), Groq via LangChain
│   │   └── db/
│   │       ├── postgres.py         # engine, session
│   │       ├── models.py           # SQLAlchemy tables
│   │       ├── mongo.py            # client, collections
│   │       └── seed.py             # seeds Postgres
│   ├── data/
│   │   ├── policies/               # sample policy PDFs
│   │   ├── erx_samples/            # JSON eRx test inputs
│   │   └── chroma/                 # vector store (gitignored)
│   └── tests/
│       ├── test_health.py
│       ├── test_graph.py
│       ├── test_tools.py
│       └── eval/
│           ├── golden_cases.json
│           └── run_eval.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   └── client.ts
        ├── pages/
        │   ├── NewCase.tsx
        │   └── CaseResult.tsx
        ├── components/
        │   ├── CoverageCard.tsx
        │   ├── PACard.tsx
        │   ├── GapsList.tsx
        │   ├── RiskSignals.tsx
        │   ├── ProviderMessage.tsx
        │   └── CitationList.tsx
        └── types/
            └── case.ts
```

## 15. Build Order
Done: setup, traced graph and tests, LLM factory, Postgres models + seed + real tools, policy RAG (ingest + retriever). Next: Mongo + case API -> live Groq tuning -> eval -> React UI -> README/diagram/tag v1.0.

## 16. v1 Non-Goals
Auth, PHI redaction, FHIR, immutable audit log, human-approval interrupts, CI, pgvector, MongoDB auth. (All v2.)

## 17. Conventions
- Never commit `.env`, keys, or real data. `.env.example` holds placeholders only (optional settings commented out).
- Tests mock the LLM; no test calls Groq. Run `python -m pytest` from `backend/`.
- No PHI in logs, traces, or error messages.
- No Docker; use local PostgreSQL and a hosted MongoDB. POSTGRES_URL must use the postgresql+psycopg:// form.
- Prefer minimal diffs; do not rewrite files that were not asked about.