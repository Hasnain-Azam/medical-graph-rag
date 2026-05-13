"""
Upload Router — handles document ingestion.

POST /api/upload
  1. Accept PDF or TXT file
  2. Save temporarily to disk
  3. Extract text → chunk → extract entities → store in Neo4j
  4. Return summary statistics
"""
import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.models import UploadResponse
from app.services.document_processor import extract_text, chunk_text
from app.services.entity_extractor import extract_entities_and_relationships
from app.services.graph_manager import graph_manager
from app.services.rag_pipeline import embed_text
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/octet-stream",  # Some browsers send this for .txt
}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_FILE_SIZE_MB = 20


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Ingest a medical document into the knowledge graph.
    Accepts PDF or plain text files up to 20MB.
    """
    settings = get_settings()

    # ── Validate file ──────────────────────────────────────────────────────────
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Please upload PDF or TXT.",
        )

    # ── Read file content ──────────────────────────────────────────────────────
    content = await file.read()

    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f}MB). Maximum is {MAX_FILE_SIZE_MB}MB.",
        )

    logger.info(f"Received file: {file.filename} ({size_mb:.2f}MB)")

    # ── Save to temp file ──────────────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(
        suffix=file_ext, delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    total_entities = 0
    total_relationships = 0
    chunks_processed = 0

    try:
        # ── Extract text ───────────────────────────────────────────────────────
        text = extract_text(tmp_path)

        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not extract any text from this file. "
                       "If it's a scanned PDF, OCR is not yet supported.",
            )

        # ── Chunk text ─────────────────────────────────────────────────────────
        chunks = chunk_text(
            text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        logger.info(f"Processing {len(chunks)} chunks...")

        # ── Process each chunk ─────────────────────────────────────────────────
        for i, chunk in enumerate(chunks):
            logger.info(f"  Chunk {i + 1}/{len(chunks)}")

            # Extract entities + relationships via LLM
            extracted = extract_entities_and_relationships(chunk)
            entities = extracted.get("entities", [])
            relationships = extracted.get("relationships", [])

            # Upsert entities with embeddings into Neo4j
            for entity in entities:
                try:
                    embedding = embed_text(
                        f"{entity['name']} {entity['description']}"
                    )
                    graph_manager.upsert_entity_simple(entity, embedding)
                except Exception as e:
                    logger.warning(f"Failed to upsert entity '{entity['name']}': {e}")

            # Upsert relationships
            for rel in relationships:
                try:
                    graph_manager.upsert_relationship(
                        rel["source_id"],
                        rel["target_id"],
                        rel["type"],
                        rel.get("properties", {}),
                    )
                except Exception as e:
                    logger.warning(f"Failed to upsert relationship: {e}")

            total_entities += len(entities)
            total_relationships += len(relationships)
            chunks_processed += 1

    finally:
        # Always clean up the temp file
        os.unlink(tmp_path)

    logger.info(
        f"Ingestion complete: {total_entities} entities, "
        f"{total_relationships} relationships across {chunks_processed} chunks."
    )

    return UploadResponse(
        message="Document processed and added to the knowledge graph successfully.",
        filename=file.filename or "unknown",
        entities_extracted=total_entities,
        relationships_extracted=total_relationships,
        chunks_processed=chunks_processed,
    )
