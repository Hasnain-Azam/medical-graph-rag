"""
RAG Pipeline — the core intelligence of the system.

Query flow:
  1. Embed the user's question with text-embedding-3-small
  2. Vector similarity search → top-k semantically relevant entity nodes
  3. Expand a 2-hop subgraph around those seed nodes
  4. Format the subgraph as a structured context string
  5. Call GPT-4o with the context to generate a grounded answer
  6. Return { answer, subgraph } to the API router
"""
import logging
from openai import OpenAI

from app.config import get_settings
from app.services.graph_manager import graph_manager

logger = logging.getLogger(__name__)


# ── Answer Generation Prompt ──────────────────────────────────────────────────────
QA_SYSTEM_PROMPT = """You are an expert medical research assistant with deep knowledge
of clinical medicine, pharmacology, genetics, and diagnostic medicine.

You will be given:
1. A user question about medical topics.
2. A KNOWLEDGE GRAPH CONTEXT extracted from uploaded medical documents.

Your task:
- Answer the question accurately and concisely based on the knowledge graph context.
- Structure your answer clearly using paragraphs. Use bullet points where appropriate.
- If the context mentions specific drugs, genes, symptoms, or treatment protocols, reference them explicitly.
- If the context is insufficient to fully answer the question, acknowledge that and provide
  what information you do have.
- Do NOT hallucinate information not present in the context.
- End with a brief "Key Entities" summary listing the most relevant entities from the graph.

Tone: Professional, clinical, informative — like a medical research brief.
"""


def embed_text(text: str) -> list[float]:
    """Generate an embedding vector for the given text using OpenAI."""
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text[:8000],  # Embedding model token limit guard
    )
    return response.data[0].embedding


def _format_graph_context(nodes: list[dict], links: list[dict]) -> str:
    """
    Convert subgraph data into a readable text context for the LLM.
    Groups entities by type for clarity.
    """
    if not nodes:
        return "No relevant entities found in the knowledge graph."

    # Group nodes by type
    by_type: dict[str, list[dict]] = {}
    for node in nodes:
        by_type.setdefault(node["type"], []).append(node)

    lines = ["=== KNOWLEDGE GRAPH CONTEXT ===\n"]

    # Entity section
    lines.append("── ENTITIES ──")
    for entity_type, type_nodes in sorted(by_type.items()):
        lines.append(f"\n[{entity_type}]")
        for n in type_nodes:
            desc = f" — {n['description']}" if n.get("description") else ""
            lines.append(f"  • {n['name']}{desc}")

    # Relationship section
    if links:
        # Build a lookup for node ID → name
        id_to_name = {n["id"]: n["name"] for n in nodes}
        lines.append("\n── RELATIONSHIPS ──")
        for link in links:
            src = id_to_name.get(link["source"], link["source"])
            tgt = id_to_name.get(link["target"], link["target"])
            lines.append(f"  {src}  ──[{link['type']}]──▶  {tgt}")

    return "\n".join(lines)


def process_query(question: str) -> dict:
    """
    Full GraphRAG pipeline for a single user question.

    Returns:
        {
            "answer":   str,
            "subgraph": {"nodes": [...], "links": [...]}
            "sources":  [entity names used as context]
        }
    """
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    # ── Step 1: Embed the question ─────────────────────────────────────────────
    logger.info(f"Processing query: {question[:100]}...")
    query_embedding = embed_text(question)

    # ── Step 2: Vector similarity search ──────────────────────────────────────
    similar_entities = graph_manager.vector_similarity_search(
        query_embedding, top_k=settings.vector_top_k
    )
    logger.info(f"Found {len(similar_entities)} similar entities via vector search.")

    seed_ids = [e["id"] for e in similar_entities]

    # ── Step 3: Expand subgraph ────────────────────────────────────────────────
    nodes, links = graph_manager.expand_subgraph(seed_ids, hops=settings.subgraph_hops)
    logger.info(f"Subgraph expanded: {len(nodes)} nodes, {len(links)} relationships.")

    # ── Step 4: Format context ─────────────────────────────────────────────────
    context = _format_graph_context(nodes, links)

    # ── Step 5: Generate answer with GPT-4o ───────────────────────────────────
    user_message = f"""Question: {question}

{context}

Please answer the question based on the knowledge graph context above."""

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    answer = response.choices[0].message.content.strip()
    sources = [e["name"] for e in similar_entities]

    logger.info("Answer generated successfully.")

    return {
        "answer": answer,
        "subgraph": {"nodes": nodes, "links": links},
        "sources": sources,
    }
