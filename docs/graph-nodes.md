# Graph nodes

## 1. Prescription extraction

`extract.py` uses an LLM and Pydantic validation to extract the drug name, NDC,
quantity, days supply, prescriber, and diagnosis from an eRx.

Output: `rx`

## 2. Coverage verification

`coverage.py` checks member eligibility under the relevant plan and date using
Python and PostgreSQL. It does not need an LLM.

Output: `coverage`, potentially `status`

## 3. Policy retrieval and interpretation

`policy.py` looks up the formulary rule, retrieves relevant policy chunks, and
interprets the supporting evidence. It checks that citations refer to retrieved
documents.

Output: `policy`

## 4. Documentation gap analysis

`gaps.py` compares the policy's documentation requirements with the information
available in the case, identifying missing clinical notes, lab results, or other
required evidence.

Output: `gaps`

## 5. Utilization checks

`utilization.py` checks refill timing, quantity limits, potential duplicate
therapy, and relevant claims history. It returns review signals rather than
asserting misuse.

Output: `utilization`

## 6. Safety validation

`guardrail.py` checks generated content for unsupported claims, invalid
citations, and prohibited approval, denial, or medication-recommendation
language. It manages the retry and safe-fallback behavior.

Output: `guardrail_passed`, `guardrail_attempts`

## 7. Provider communication

`provider_msg.py` drafts a fax, email, or portal message requesting specific
missing documentation. It does not send the message.

Output: `provider_msg`

## 8. Final summary

`summary.py` combines validated outputs into the response consumed by the React
dashboard. It preserves manual-review and stopped statuses.

Output: `summary`
