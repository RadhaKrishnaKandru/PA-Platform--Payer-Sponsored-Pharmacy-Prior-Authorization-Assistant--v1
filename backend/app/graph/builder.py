
"""Build and compile the PA Platform LangGraph workflow."""

from langgraph.graph import StateGraph, START, END

from app.graph.state import CaseState

from app.graph.nodes.extract import extract_node
from app.graph.nodes.coverage import coverage_node
from app.graph.nodes.policy import policy_node
from app.graph.nodes.gaps import gaps_node
from app.graph.nodes.utilization import utilization_node
from app.graph.nodes.guardrail import guardrail_node
from app.graph.nodes.provider_msg import provider_msg_node
from app.graph.nodes.summary import summary_node


def _value(obj, key: str, default=None):
    """Read a field from a Pydantic model or dictionary."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def route_after_coverage(state: CaseState) -> str:
    """Route according to the coverage verification result."""
    coverage = state.get("coverage")
    status = _value(coverage, "status", "unknown")

    if status == "active":
        return "policy"

    return "summary"


def route_after_policy(state: CaseState) -> list[str]:
    """Route according to policy availability and PA requirements."""
    policy = state.get("policy")

    policy_status = _value(policy, "status", "not_found")
    pa_required = _value(policy, "pa_required")

    if policy_status == "found" and pa_required is True:
        return ["gaps", "utilization"]
    return ["utilization"]


def route_after_utilization(state: CaseState) -> list[str]:
    """Summarize non-PA cases; PA cases continue after the parallel join."""
    policy = state.get("policy")
    if (
        _value(policy, "status") == "found"
        and _value(policy, "pa_required") is True
    ):
        return []
    return ["summary"]


def route_after_guardrail(state: CaseState) -> str:
    """Retry message generation once if guardrail validation fails."""
    if state.get("guardrail_passed", False):
        return "summary"

    attempts = state.get("guardrail_attempts", 0)

    if attempts < 2:
        return "provider_msg"

    return "summary"


def build_graph():
    """Construct and compile the PA case-processing graph."""
    graph = StateGraph(CaseState)

    graph.add_node("extract", extract_node)
    graph.add_node("coverage", coverage_node)
    graph.add_node("policy", policy_node)
    graph.add_node("gaps", gaps_node)
    graph.add_node("utilization", utilization_node)
    graph.add_node("provider_msg", provider_msg_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("summary", summary_node)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "coverage")

    graph.add_conditional_edges(
        "coverage",
        route_after_coverage,
        {
            "policy": "policy",
            "summary": "summary",
        },
    )

    graph.add_conditional_edges(
        "policy",
        route_after_policy,
        {
            "gaps": "gaps",
            "utilization": "utilization",
        },
    )

    graph.add_edge(["gaps", "utilization"], "provider_msg")
    graph.add_conditional_edges("utilization", route_after_utilization)
    graph.add_edge("provider_msg", "guardrail")

    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {
            "provider_msg": "provider_msg",
            "summary": "summary",
        },
    )

    graph.add_edge("summary", END)

    return graph.compile()


pa_graph = build_graph()
