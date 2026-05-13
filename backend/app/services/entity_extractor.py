"""
Entity Extractor — calls the Gemini REST API directly via httpx to extract
medical entities and relationships from text chunks as structured JSON.

Entity types: Disease, Drug, Gene, Symptom, TreatmentProtocol, BloodTest
"""
import ast
import hashlib
import json
import logging
import re
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 65   # seconds to wait on first 429 hit

SYSTEM_PROMPT = """You are a biomedical knowledge graph expert.
Extract named medical entities and relationships from the text.
Return ONLY raw JSON — no markdown, no code fences, no explanation.

Entity types (use EXACTLY these): Disease, Drug, Gene, Symptom, TreatmentProtocol, BloodTest

Relationship types (UPPERCASE): TREATS, CAUSES, INHIBITS, ASSOCIATED_WITH,
DIAGNOSES, MEASURES, PART_OF, INDICATES, PRESCRIBED_FOR, MONITORS

Return this exact structure:
{
  "entities": [
    {"name": "...", "type": "EntityType", "description": "one sentence", "properties": {}}
  ],
  "relationships": [
    {"source_name": "...", "source_type": "...", "target_name": "...", "target_type": "...", "type": "RELATIONSHIP_TYPE", "properties": {}}
  ]
}

Rules:
- Only extract entities explicitly in the text
- Names must match exactly between entities and relationships
- Return {"entities": [], "relationships": []} if nothing found
- Output raw JSON only, starting with {"""


def make_entity_id(name: str, entity_type: str) -> str:
    """Deterministic ID so the same entity merges across document chunks."""
    key = f"{entity_type.lower()}:{name.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _parse_llm_json(raw: str) -> dict:
    """Robustly parse JSON from an LLM response."""
    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part:
                raw = part
                break

    # Extract outermost { } block
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group(0)

    raw = raw.strip()

    # Try standard JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: Python-style single-quoted dicts
    try:
        result = ast.literal_eval(raw)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    # Last resort: replace single quotes
    try:
        fixed = re.sub(r"(?<![\\])'", '"', raw)
        return json.loads(fixed)
    except Exception:
        pass

    raise json.JSONDecodeError("Could not parse LLM response as JSON", raw, 0)


def _call_gemini(prompt: str, system: str, settings) -> str:
    """
    Direct HTTPS call to the Gemini generateContent REST endpoint.
    Returns the text content of the first candidate part.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_chat_model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 4096,
            "thinkingConfig": {"thinkingBudget": 0},   # disable thinking for fast JSON output
        },
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload)

    if resp.status_code == 429:
        raise RuntimeError(f"429 RATE_LIMIT: {resp.text[:200]}")
    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return ""

    text = ""
    for part in candidates[0].get("content", {}).get("parts", []):
        if not part.get("thought", False) and part.get("text"):
            text += part["text"]
    return text.strip()


def extract_entities_and_relationships(text_chunk: str) -> dict:
    """
    Call Gemini REST API on a text chunk, return structured entity/relationship data.
    """
    settings = get_settings()
    prompt = f"Extract medical entities and relationships from this text:\n\n{text_chunk}"

    for attempt in range(MAX_RETRIES):
        try:
            raw = _call_gemini(prompt, SYSTEM_PROMPT, settings)

            if not raw:
                logger.warning("Model returned empty response — skipping chunk.")
                return {"entities": [], "relationships": []}

            data = _parse_llm_json(raw)
            break

        except json.JSONDecodeError as e:
            logger.error(f"Could not parse model response as JSON: {e}")
            logger.debug(f"Raw was: {raw[:300] if 'raw' in dir() else '(not set)'}")
            return {"entities": [], "relationships": []}

        except RuntimeError as e:
            err_str = str(e)
            if "429" in err_str or "RATE_LIMIT" in err_str:
                wait = RETRY_BASE_DELAY * (attempt + 1)
                logger.warning(f"Rate limit — waiting {wait}s (retry {attempt+1}/{MAX_RETRIES})...")
                time.sleep(wait)
                if attempt == MAX_RETRIES - 1:
                    logger.error("Max retries exceeded.")
                    return {"entities": [], "relationships": []}
            else:
                logger.error(f"API call failed: {e}")
                return {"entities": [], "relationships": []}
    else:
        return {"entities": [], "relationships": []}

    # ── Normalize entities — add deterministic IDs ─────────────────────────────
    entities: list[dict] = []
    entity_lookup: dict[tuple, str] = {}

    for raw_entity in data.get("entities", []):
        name = raw_entity.get("name", "").strip()
        etype = raw_entity.get("type", "").strip()
        if not name or not etype:
            continue

        entity_id = make_entity_id(name, etype)
        entity_lookup[(name.lower(), etype)] = entity_id
        entities.append({
            "id": entity_id,
            "name": name,
            "type": etype,
            "description": raw_entity.get("description", ""),
            "properties": raw_entity.get("properties", {}),
        })

    # ── Normalize relationships ────────────────────────────────────────────────
    relationships: list[dict] = []

    for raw_rel in data.get("relationships", []):
        src_name = raw_rel.get("source_name", "").strip()
        src_type = raw_rel.get("source_type", "").strip()
        tgt_name = raw_rel.get("target_name", "").strip()
        tgt_type = raw_rel.get("target_type", "").strip()
        rel_type = raw_rel.get("type", "").strip()

        if not all([src_name, src_type, tgt_name, tgt_type, rel_type]):
            continue

        src_id = entity_lookup.get((src_name.lower(), src_type), make_entity_id(src_name, src_type))
        tgt_id = entity_lookup.get((tgt_name.lower(), tgt_type), make_entity_id(tgt_name, tgt_type))

        relationships.append({
            "source_id": src_id,
            "target_id": tgt_id,
            "type": rel_type,
            "properties": raw_rel.get("properties", {}),
        })

    logger.info(f"Extracted {len(entities)} entities and {len(relationships)} relationships.")
    return {"entities": entities, "relationships": relationships}
