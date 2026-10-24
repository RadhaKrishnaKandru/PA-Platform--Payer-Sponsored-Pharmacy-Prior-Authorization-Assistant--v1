"""Graph integration tests with deterministic synthetic dependencies."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

# The RAG implementation is not part of this build step; graph behavior is
# tested with synthetic retrieval results below.
rag_package = ModuleType("app.rag")
rag_package.__path__ = []
retriever_module = ModuleType("app.rag.retriever")
retriever_module.retrieve_policy_chunks = lambda **_kwargs: []
sys.modules.setdefault("app.rag", rag_package)
sys.modules.setdefault("app.rag.retriever", retriever_module)

from app.graph.builder import pa_graph
from app.graph.nodes import coverage, gaps, policy, provider_msg, utilization
from app.graph.nodes.gaps import GapAnalysis
from app.graph.nodes._trace import traced
from app.graph.state import (
    CoverageResult,
    PolicyCitation,
    PolicyResult,
    ProviderMessage,
)


class FakeChain:
    def __init__(self, schema: type, policy_status: str, pa_required: bool | None):
        self.schema = schema
        self.policy_status = policy_status
        self.pa_required = pa_required

    def invoke(self, _input: dict[str, object]) -> object:
        if self.schema is PolicyResult:
            if self.policy_status != "found":
                return PolicyResult(
                    status=self.policy_status,
                    pa_required=None,
                    reasons=["No applicable policy was found."],
                    citations=[],
                )
            return PolicyResult(
                status="found",
                pa_required=self.pa_required,
                reasons=["Synthetic policy evidence."],
                citations=[
                    PolicyCitation(
                        document="synthetic-policy.pdf",
                        page=1,
                        section="Eligibility",
                    )
                ],
            )
        if self.schema is GapAnalysis:
            return GapAnalysis()
        if self.schema is ProviderMessage:
            return ProviderMessage(
                message_type="fax",
                content="Please provide the documentation listed in the policy.",
            )
        raise AssertionError(f"Unexpected structured output schema: {self.schema}")


class FakeStructuredLLM:
    def __init__(self, schema: type, policy_status: str, pa_required: bool | None):
        self.schema = schema
        self.policy_status = policy_status
        self.pa_required = pa_required


class FakeLLM:
    def __init__(self, policy_status: str, pa_required: bool | None):
        self.policy_status = policy_status
        self.pa_required = pa_required

    def with_structured_output(self, schema: type) -> FakeStructuredLLM:
        return FakeStructuredLLM(schema, self.policy_status, self.pa_required)


class FakePrompt:
    def __or__(self, structured_llm: FakeStructuredLLM) -> FakeChain:
        return FakeChain(
            structured_llm.schema,
            structured_llm.policy_status,
            structured_llm.pa_required,
        )


@pytest.fixture
def configure_graph(monkeypatch: pytest.MonkeyPatch):
    def configure(
        *,
        policy_status: str = "found",
        pa_required: bool | None = True,
        coverage_status: str = "active",
    ) -> None:
        fake_llm = FakeLLM(policy_status, pa_required)
        monkeypatch.setattr(policy, "get_llm", lambda *_args, **_kwargs: fake_llm)
        monkeypatch.setattr(gaps, "get_llm", lambda *_args, **_kwargs: fake_llm)
        monkeypatch.setattr(
            provider_msg, "get_llm", lambda *_args, **_kwargs: fake_llm
        )
        monkeypatch.setattr(policy, "POLICY_PROMPT", FakePrompt())
        monkeypatch.setattr(gaps, "GAPS_PROMPT", FakePrompt())
        monkeypatch.setattr(provider_msg, "PROVIDER_MESSAGE_PROMPT", FakePrompt())
        monkeypatch.setattr(
            policy,
            "retrieve_policy_chunks",
            lambda **_kwargs: (
                []
                if policy_status != "found"
                else [
                    SimpleNamespace(
                        page_content="Synthetic policy excerpt.",
                        metadata={
                            "document": "synthetic-policy.pdf",
                            "page": 1,
                            "section": "Eligibility",
                        },
                    )
                ]
            ),
        )
        monkeypatch.setattr(
            gaps,
            "retrieve_policy_chunks",
            lambda **_kwargs: [
                SimpleNamespace(
                    page_content="Synthetic documentation requirement.",
                    metadata={
                        "document": "synthetic-policy.pdf",
                        "page": 1,
                        "section": "Eligibility",
                    },
                )
            ],
        )
        monkeypatch.setattr(
            coverage,
            "check_member_coverage",
            lambda _rx: CoverageResult(
                status=coverage_status,
                member_id="SYNTH-MEMBER-001",
                plan_id="SYNTH-PLAN-001",
            ),
        )
        monkeypatch.setattr(utilization, "get_member_fills", lambda _member_id: [])
        monkeypatch.setattr(utilization, "get_member_claims", lambda _member_id: [])
        monkeypatch.setattr(
            utilization, "get_formulary_entry", lambda *_args, **_kwargs: None
        )

    return configure


def _case() -> dict[str, object]:
    return {
        "erx": {
            "drug": "Example Medication",
            "ndc": "00000-0000-00",
            "quantity": 30,
            "days_supply": 30,
            "prescriber": "Synthetic Provider",
            "diagnosis": "Synthetic diagnosis",
        }
    }


def _assert_trace(result: dict[str, object], expected_nodes: set[str]) -> None:
    trace = result["trace"]
    nodes = [event.node for event in trace]
    assert len(nodes) == len(expected_nodes)
    assert set(nodes) == expected_nodes
    assert len(nodes) == len(set(nodes))


def test_inactive_coverage_stops_before_policy(configure_graph) -> None:
    configure_graph(coverage_status="inactive")

    result = pa_graph.invoke(_case())

    assert result["status"] == "stopped"
    assert result["summary"].status == "stopped"
    _assert_trace(result, {"extract", "coverage", "summary"})


def test_pa_required_runs_parallel_checks_and_guardrail(configure_graph) -> None:
    configure_graph(policy_status="found", pa_required=True)

    result = pa_graph.invoke(_case())

    assert result["status"] == "ok"
    assert result["summary"].status == "ok"
    _assert_trace(
        result,
        {
            "extract",
            "coverage",
            "policy",
            "gaps",
            "utilization",
            "provider_msg",
            "guardrail",
            "summary",
        },
    )


def test_pa_not_required_skips_provider_message(configure_graph) -> None:
    configure_graph(policy_status="found", pa_required=False)

    result = pa_graph.invoke(_case())

    assert result["status"] == "ok"
    assert result["summary"].status == "ok"
    assert "provider_msg" not in result
    _assert_trace(
        result,
        {"extract", "coverage", "policy", "utilization", "summary"},
    )


def test_policy_not_found_requires_manual_review(configure_graph) -> None:
    configure_graph(policy_status="not_found", pa_required=None)

    result = pa_graph.invoke(_case())

    assert result["status"] == "needs_manual_review"
    assert result["summary"].status == "needs_manual_review"
    assert "provider_msg" not in result
    _assert_trace(
        result,
        {"extract", "coverage", "policy", "utilization", "summary"},
    )


def test_parallel_node_errors_merge_and_complete(configure_graph, monkeypatch) -> None:
    configure_graph(policy_status="found", pa_required=True)

    def raise_gap_error(**_kwargs):
        raise ValueError("Synthetic retrieval failure.")

    def raise_utilization_error(_member_id):
        raise ValueError("Synthetic fill lookup failure.")

    monkeypatch.setattr(gaps, "retrieve_policy_chunks", raise_gap_error)
    monkeypatch.setattr(utilization, "get_member_fills", raise_utilization_error)

    result = pa_graph.invoke(_case())

    assert result["status"] == "needs_manual_review"
    assert result["summary"].status == "needs_manual_review"
    _assert_trace(
        result,
        {
            "extract",
            "coverage",
            "policy",
            "gaps",
            "utilization",
            "provider_msg",
            "guardrail",
            "summary",
        },
    )


def test_manual_review_return_is_traced_as_success() -> None:
    @traced("test_node")
    def node(_state: dict) -> dict:
        return {"status": "needs_manual_review"}

    result = node({})

    assert result["trace"][0].outcome == "success"
    assert result["trace"][0].error_category == "manual_review"
