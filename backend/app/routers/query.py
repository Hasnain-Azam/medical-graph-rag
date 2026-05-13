"""
Query Router — handles knowledge graph querying and retrieval.

POST /api/query   → GraphRAG: answer + subgraph visualization data
GET  /api/graph   → Full graph overview (for the dashboard)
GET  /api/health  → Health check with Neo4j status
"""
import logging

from fastapi import APIRouter, HTTPException

from app.models import (
    ChatRequest,
    ChatResponse,
    GraphData,
    GraphStatsResponse,
    HealthResponse,
    Entity,
    Relationship,
)
from app.services.graph_manager import graph_manager
from app.services.rag_pipeline import process_query
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=ChatResponse)
async def query_graph(request: ChatRequest):
    """
    GraphRAG endpoint — runs the full pipeline:
      embed question → vector search → subgraph expansion → LLM answer
    Returns a natural language answer + subgraph data for visualization.
    """
    if not graph_manager.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j is not available.")

    try:
        result = process_query(request.question)
    except Exception as e:
        logger.error(f"Query pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}",
        )

    # Deserialize into response models
    nodes = [Entity(**n) for n in result["subgraph"]["nodes"]]
    links = [
        Relationship(
            source=lnk["source"],
            target=lnk["target"],
            type=lnk["type"],
            properties=lnk.get("properties", {}),
        )
        for lnk in result["subgraph"]["links"]
    ]

    return ChatResponse(
        answer=result["answer"],
        subgraph=GraphData(nodes=nodes, links=links),
        sources=result.get("sources", []),
    )


@router.get("/graph", response_model=GraphStatsResponse)
async def get_full_graph():
    """
    Return the full knowledge graph for the dashboard overview panel.
    Capped at 200 nodes / 500 relationships for performance.
    """
    if not graph_manager.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j is not available.")

    try:
        nodes_raw, links_raw = graph_manager.get_full_graph()
        stats = graph_manager.get_graph_stats()
    except Exception as e:
        logger.error(f"Graph retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    nodes = [Entity(**n) for n in nodes_raw]
    links = [
        Relationship(
            source=lnk["source"],
            target=lnk["target"],
            type=lnk["type"],
            properties=lnk.get("properties", {}),
        )
        for lnk in links_raw
    ]

    return GraphStatsResponse(
        total_nodes=stats["total_nodes"],
        total_relationships=stats["total_relationships"],
        node_types=stats["node_types"],
        relationship_types=stats["relationship_types"],
        graph=GraphData(nodes=nodes, links=links),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Lightweight health check — verifies Neo4j connectivity."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        neo4j_connected=graph_manager.is_connected(),
        environment=settings.environment,
    )
