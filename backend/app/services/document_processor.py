"""
Document Processor — handles PDF and plain-text extraction, then splits
the content into overlapping chunks for LLM processing.
"""
import logging
import re
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> str:
    """
    Route to the correct extractor based on file extension.
    Returns the full raw text of the document.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_from_pdf(file_path)
    elif suffix in (".txt", ".md"):
        return _extract_from_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Please upload PDF or TXT.")


def _extract_from_pdf(file_path: str) -> str:
    """Extract text from every page of a PDF using pdfplumber."""
    pages_text: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        logger.info(f"PDF has {len(pdf.pages)} pages: {file_path}")
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text.strip())
            else:
                logger.warning(f"Page {i + 1} returned no text (may be image-based).")

    full_text = "\n\n".join(pages_text)
    logger.info(f"Extracted {len(full_text)} characters from PDF.")
    return full_text


def _extract_from_text(file_path: str) -> str:
    """Read a plain text file with UTF-8 encoding."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    logger.info(f"Read {len(content)} characters from text file.")
    return content


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks that respect sentence boundaries.

    Strategy:
    1. Clean the text (normalize whitespace).
    2. Split on sentence-ending punctuation to avoid cutting mid-sentence.
    3. Greedily accumulate sentences until chunk_size is reached.
    4. Carry the last `overlap` characters into the next chunk for context continuity.
    """
    # 1. Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= chunk_size:
        return [text]

    # 2. Split into sentences (crude but effective for medical text)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_length + sentence_len > chunk_size and current_chunk:
            # Flush current chunk
            chunk_text_str = " ".join(current_chunk)
            chunks.append(chunk_text_str)

            # Start next chunk with overlap: keep sentences from the tail
            overlap_text = chunk_text_str[-overlap:] if len(chunk_text_str) > overlap else chunk_text_str
            current_chunk = [overlap_text, sentence]
            current_length = len(overlap_text) + sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    logger.info(f"Split text into {len(chunks)} chunks (size={chunk_size}, overlap={overlap}).")
    return chunks
