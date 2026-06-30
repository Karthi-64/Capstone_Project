# v3/graph.py — LangGraph pipeline, dynamic 2-step or 4-step

from langgraph.graph import END, START, StateGraph

from v3.nodes.analyze import analyze_node
from v3.nodes.generate import generate_node
from v3.nodes.ingest import ingest_node
from v3.nodes.review import review_node
from v3.state import PipelineState


def _route_after_ingest(state: PipelineState) -> str:
    if state.get("ingest_error"):
        return "end"
    if state.get("step_count") == 4:
        return "analyze"
    return "generate"


def _route_after_generate(state: PipelineState) -> str:
    if state.get("generate_error"):
        return "end"
    if state.get("step_count") == 4:
        return "review"
    return "end"


def build_graph(step_count: int = 2):
    """
    step_count == 2 → Ingest → Generate
    step_count == 4 → Ingest → Analyze → Generate → Review
    """
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("generate", generate_node)

    if step_count == 4:
        graph.add_node("analyze", analyze_node)
        graph.add_node("review", review_node)

        graph.add_edge(START, "ingest")
        graph.add_conditional_edges(
            "ingest",
            _route_after_ingest,
            {"analyze": "analyze", "end": END},
        )
        graph.add_edge("analyze", "generate")
        graph.add_conditional_edges(
            "generate",
            _route_after_generate,
            {"review": "review", "end": END},
        )
        graph.add_edge("review", END)
    else:
        graph.add_edge(START, "ingest")
        graph.add_conditional_edges(
            "ingest",
            _route_after_ingest,
            {"generate": "generate", "end": END},
        )
        graph.add_edge("generate", END)

    return graph.compile()
