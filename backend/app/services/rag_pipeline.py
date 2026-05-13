"""
RAG Pipeline — GraphRAG query flow using Gemini REST API directly.

1. Embed question  →  gemini-embedding-001 REST endpoint
2. Vector search   →  Neo4j vector index
3. Expand subgraph →  2-hop expansion
4. Format context  →  structured text
5. Generate answer →  Gemini generateContent REST endpoint
"""
import logging
import httpx

from app.config import get_settings
from app.services.graph_manager import graph_manager

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """You are an expert medical research assistant with deep knowledge
of clinical medicine, pharmacology, genetics, and diagnostic medicine.

You will be given a user question and a KNOWLEDGE GRAPH CONTEXT from uploaded medical documents.

Answer the question accurately based on the context. Use bullet points where helpful.
Reference specific drugs, genes, symptoms, and protocols mentioned in the context.
End with a "Key Entities" summary of the most relevant graph nodes.
Do NOT hallucinate information not in the context.
Tone: professional and clinical."""


def embed_text(text: str, task: str = "RETRIEVAL_QUERY") -> list[float]:
    """Embed text using Gemini embedding REST API. Returns a list of floats."""
    settings = get_settings()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_embedding_model}:embedContent"
        f"?key={settings.gemini_api_key}"
    )
    payload = {
        "model": f"models/{settings.gemini_embedding_model}",
        "content": {"parts": [{"text": text[:8000]}]},
        "taskType": task,
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Embed API error {resp.status_code}: {resp.text[:200]}")

    return resp.json()["embedding"]["values"]


def _call_gemini_chat(message: str, system: str, settings) -> str:
    """Direct REST call to Gemini generateContent."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_chat_model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": message}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500},
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Chat API error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    text = ""
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if not part.get("thought", False) and part.get("text"):
            text += part["text"]
    return text.strip()


def _format_graph_context(nodes: list[dict], links: list[dict]) -> str:
    if not nodes:
        return "No relevant entities found in the knowledge graph."

    by_type: dict[str, list[dict]] = {}
    for node in nodes:
        by_type.setdefault(node["type"], []).append(node)

    lines = ["=== KNOWLEDGE GRAPH CONTEXT ===\n", "── ENTITIES ──"]
    for entity_type, type_nodes in sorted(by_type.items()):
        lines.append(f"\n[{entity_type}]")
        for n in type_nodes:
            desc = f" — {n['description']}" if n.get("description") else ""
            lines.append(f"  • {n['name']}{desc}")

    if links:
        id_to_name = {n["id"]: n["name"] for n in nodes}
        lines.append("\n── RELATIONSHIPS ──")
        for link in links:
            src = id_to_name.get(link["source"], link["source"])
            tgt = id_to_name.get(link["target"], link["target"])
            lines.append(f"  {src}  ──[{link['type']}]──▶  {tgt}")

    return "\n".join(lines)


def process_query(question: str) -> dict:
    """Full GraphRAG pipeline for a user question."""
    settings = get_settings()

    logger.info(f"Processing query: {question[:100]}...")

    # 1. Embed question
    query_embedding = embed_text(question, task="RETRIEVAL_QUERY")

    # 2. Vector similarity search
    similar_entities = graph_manager.vector_similarity_search(
        query_embedding, top_k=settings.vector_top_k
    )
    logger.info(f"Found {len(similar_entities)} similar entities.")
    seed_ids = [e["id"] for e in similar_entities]

    # 3. Expand subgraph
    nodes, links = graph_manager.expand_subgraph(seed_ids, hops=settings.subgraph_hops)
    logger.info(f"Subgraph: {len(nodes)} nodes, {len(links)} relationships.")

    # 4. Format context
    context = _format_graph_context(nodes, links)

    # 5. Generate answer
    user_message = f"Question: {question}\n\n{context}\n\nAnswer based on the knowledge graph above."
    answer = _call_gemini_chat(user_message, QA_SYSTEM_PROMPT, settings)

    logger.info("Answer generated.")
    return {
        "answer": answer,
        "subgraph": {"nodes": nodes, "links": links},
        "sources": [e["name"] for e in similar_entities],
    }
