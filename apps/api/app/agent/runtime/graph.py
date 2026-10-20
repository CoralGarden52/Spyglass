from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.agents.analysis import AnalysisNodes
from app.agent.agents.collection import CollectionNodes
from app.agent.agents.reporting import ReportingNodes
from app.agent.runtime.context import NodeContext
from app.agent.runtime.state import ResearchState


def route_review(state: ResearchState) -> str:
    review = state.get("review_result") or {}
    return str(review.get("next_target")) if review.get("status") == "repair" else "finish"


def build_graph(
    context: NodeContext, checkpoint: BaseCheckpointSaver[Any], max_repairs: int
) -> CompiledStateGraph[ResearchState, None, ResearchState, ResearchState]:
    collection = CollectionNodes(context)
    analysis = AnalysisNodes(context)
    reporting = ReportingNodes(context, max_repairs)
    graph = StateGraph(ResearchState)
    for name, node in [
        ("planner", collection.planner),
        ("resolver", collection.resolver),
        ("collector", collection.collector),
        ("normalizer", collection.normalizer),
        ("analyse", analysis.analyse),
        ("product", analysis.product),
        ("pricing", analysis.pricing),
        ("sentiment", analysis.sentiment),
        ("synthesis", analysis.synthesis),
        ("writer", reporting.writer),
        ("reviewer", reporting.reviewer),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "resolver")
    graph.add_edge("resolver", "collector")
    graph.add_edge("collector", "normalizer")
    graph.add_edge("normalizer", "analyse")
    for name in ("product", "pricing", "sentiment"):
        graph.add_edge("analyse", name)
    graph.add_edge(["product", "pricing", "sentiment"], "synthesis")
    graph.add_edge("synthesis", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        route_review,
        {"collector": "collector", "analyst": "analyse", "writer": "writer", "finish": END},
    )
    return graph.compile(checkpointer=checkpoint)
