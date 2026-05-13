"""
Entity Extractor — uses Gemini to extract medical entities and their
relationships from text chunks, returning structured JSON.

Entity types: Disease, Drug, Gene, Symptom, TreatmentProtocol, BloodTest
Relationship types: TREATS, CAUSES, INHIBITS, ASSOCIATED_WITH,
                    DIAGNOSES, MEASURES, PART_OF, INDICATES, PRESCRIBED_FOR, MONITORS
"""
import hashlib
import json
import logging
import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── System Prompt ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a biomedical knowledge graph expert.

Your job is to extract named medical entities and their relationships from the provided text
and return ONLY a valid JSON object — no markdown, no explanation, just raw JSON.

=== ENTITY TYPES ===
Extract entities belonging to EXACTLY these types:
- Disease        : Medical conditions (e.g., Type 2 Diabetes, Hypertension, COVID-19)
- Drug           : Medications and compounds (e.g., Metformin, Insulin, Aspirin)
- Gene           : Genetic markers or genes (e.g., TCF7L2, BRCA1, HLA-DR)
- Symptom        : Clinical signs/symptoms (e.g., Fatigue, Polyuria, Chest Pain)
- TreatmentProtocol : Clinical guidelines or treatment plans (e.g., ADA Diabetes Protocol)
- BloodTest      : Lab tests and biomarkers (e.g., HbA1c, Fasting Glucose, CBC)

=== RELATIONSHIP TYPES ===
Use ONLY these relationship types (uppercase):
- TREATS            : Drug → Disease
- CAUSES            : Disease/Drug → Symptom or Disease
- INHIBITS          : Drug → Gene or mechanism
- ASSOCIATED_WITH   : Gene ↔ Disease
- DIAGNOSES         : BloodTest → Disease
- MEASURES          : BloodTest → Gene or biomarker
- PART_OF           : Drug/BloodTest → TreatmentProtocol
- INDICATES         : BloodTest result → Disease severity
- PRESCRIBED_FOR    : Drug → Disease (alternative to TREATS with dosage context)
- MONITORS          : BloodTest → Disease progression

=== OUTPUT FORMAT ===
Return ONLY this JSON structure:
{
  "entities": [
    {
      "name": "entity name as it appears in text",
      "type": "EntityType",
      "description": "one sentence description",
      "properties": {}
    }
  ],
  "relationships": [
    {
      "source_name": "exact source entity name",
      "source_type": "SourceEntityType",
      "target_name": "exact target entity name",
      "target_type": "TargetEntityType",
      "type": "RELATIONSHIP_TYPE",
      "properties": {}
    }
  ]
}

=== RULES ===
1. Only extract entities explicitly mentioned in the text.
2. Entity names must match exactly between entities[] and relationships[].
3. Be precise with entity types — do not invent new types.
4. Return an empty list if nothing is found: {"entities": [], "relationships": []}
5. Properties can include dosage, unit, reference_range, severity, etc. where available.
"""


def make_entity_id(name: str, entity_type: str) -> str:
    """Deterministic ID so the same entity merges across document chunks."""
    key = f"{entity_type.lower()}:{name.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def extract_entities_and_relationships(text_chunk: str) -> dict:
    """
    Call Gemini on a text chunk and return structured entity/relationship data.

    Returns:
        {
            "entities":      [{"id", "name", "type", "description", "properties"}],
            "relationships": [{"source_id", "target_id", "type", "properties"}]
        }
    """
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name=settings.gemini_chat_model,
        system_instruction=SYSTEM_PROMPT,
    )

    prompt = f"Extract medical entities and relationships from this text:\n\n{text_chunk}"

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=4096,
            ),
        )
        raw = response.text.strip()
        data = json.loads(raw)

    except json.JSONDecodeError as e:
        logger.error(f"Model returned invalid JSON: {e}")
        return {"entities": [], "relationships": []}
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return {"entities": [], "relationships": []}

    # ── Normalize entities — add deterministic IDs ─────────────────────────────
    entities: list[dict] = []
    entity_lookup: dict[tuple, str] = {}   # (name_lower, type) → id

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

    # ── Normalize relationships — resolve IDs from lookup ─────────────────────
    relationships: list[dict] = []

    for raw_rel in data.get("relationships", []):
        src_name = raw_rel.get("source_name", "").strip()
        src_type = raw_rel.get("source_type", "").strip()
        tgt_name = raw_rel.get("target_name", "").strip()
        tgt_type = raw_rel.get("target_type", "").strip()
        rel_type = raw_rel.get("type", "").strip()

        if not all([src_name, src_type, tgt_name, tgt_type, rel_type]):
            continue

        src_id = entity_lookup.get(
            (src_name.lower(), src_type),
            make_entity_id(src_name, src_type),
        )
        tgt_id = entity_lookup.get(
            (tgt_name.lower(), tgt_type),
            make_entity_id(tgt_name, tgt_type),
        )

        relationships.append({
            "source_id": src_id,
            "target_id": tgt_id,
            "type": rel_type,
            "properties": raw_rel.get("properties", {}),
        })

    logger.info(
        f"Extracted {len(entities)} entities and {len(relationships)} relationships from chunk."
    )
    return {"entities": entities, "relationships": relationships}
