"""
rag.py -- Retrieval-Augmented Generation knowledge system for Eco-Router.

PHASE D: Lightweight RAG using BM25-style TF-IDF scoring.
No vector database required. No embeddings API. No external dependencies.

Architecture:
  - Documents: markdown files in knowledge/ directory
  - Chunking: paragraph-level (splits on double newlines)
  - Indexing: TF-IDF term frequency in-memory at startup
  - Retrieval: BM25-approximate scoring against query terms
  - Synthesis: chunks passed to Gemini or demo-mode summary

This keeps the system fully functional without any paid API for retrieval.
Vector-based retrieval (e.g. Vertex AI Matching Engine) can be added later
as a drop-in upgrade to the retrieve() function.

Usage:
    from eco_router.rag import retrieve, get_index_status

    chunks = await retrieve("what is carbon-aware computing?", top_k=3)
    for chunk in chunks:
        print(chunk.source, chunk.score, chunk.content[:200])
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# ── Configuration ─────────────────────────────────────────────────────────────

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"
MAX_CHUNK_WORDS = 150       # chunk size in words
MIN_CHUNK_WORDS = 10        # discard tiny chunks
TOP_K_DEFAULT = 3           # default number of retrieved chunks
BM25_K1 = 1.5               # BM25 term frequency saturation
BM25_B = 0.75               # BM25 length normalisation

# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class Chunk:
    source: str         # filename without extension
    chunk_id: int       # index within document
    content: str        # raw text
    tokens: list[str]   # lowercased, cleaned tokens
    score: float = 0.0  # filled by retrieve()


@dataclass
class KnowledgeIndex:
    chunks: list[Chunk] = field(default_factory=list)
    doc_freq: dict[str, int] = field(default_factory=dict)   # term -> num chunks containing it
    avg_chunk_len: float = 0.0
    is_loaded: bool = False
    source_files: list[str] = field(default_factory=list)


# Singleton index — loaded once at startup
_index = KnowledgeIndex()


# ── Text Processing ───────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "of", "to", "and", "or", "for",
    "on", "at", "by", "as", "be", "was", "are", "were", "been", "that",
    "this", "with", "not", "but", "from", "have", "has", "had", "its",
    "than", "then", "they", "their", "there", "when", "where", "which",
    "who", "will", "would", "can", "could", "should", "may", "might",
    "do", "does", "did", "so", "if", "we", "you", "i", "he", "she",
})


def tokenize(text: str) -> list[str]:
    """Lowercase, remove punctuation, remove stop words, min length 2."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if t not in _STOP_WORDS and len(t) >= 2]


def split_into_chunks(text: str, source: str) -> list[Chunk]:
    """Split a document into paragraph-level chunks."""
    # Split on double newlines (paragraph breaks)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks = []
    chunk_id = 0
    current_words: list[str] = []

    for para in paragraphs:
        # Skip markdown headers and separator lines (---, ===)
        if para.startswith("#"):
            continue
        if re.match(r"^[-=|]+$", para.strip()):
            continue  # table separator row
        words = para.split()
        if not words:
            continue

        current_words.extend(words)

        # Flush chunk when it hits target size
        if len(current_words) >= MAX_CHUNK_WORDS:
            content = " ".join(current_words)
            tokens = tokenize(content)
            if tokens:
                chunks.append(Chunk(
                    source=source,
                    chunk_id=chunk_id,
                    content=content,
                    tokens=tokens,
                ))
                chunk_id += 1
            current_words = []

    # Flush remaining words
    if len(current_words) >= MIN_CHUNK_WORDS:
        content = " ".join(current_words)
        tokens = tokenize(content)
        if tokens:
            chunks.append(Chunk(
                source=source,
                chunk_id=chunk_id,
                content=content,
                tokens=tokens,
            ))

    return chunks


# ── Indexing ──────────────────────────────────────────────────────────────────

def build_index() -> KnowledgeIndex:
    """
    Load all .md files from knowledge/ and build the BM25 index.
    Called once at startup (or lazily on first retrieve()).
    """
    idx = KnowledgeIndex()

    if not KNOWLEDGE_DIR.exists():
        logger.warning(f"[RAG] Knowledge directory not found: {KNOWLEDGE_DIR}")
        idx.is_loaded = True
        return idx

    md_files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not md_files:
        logger.warning(f"[RAG] No .md files in {KNOWLEDGE_DIR}")
        idx.is_loaded = True
        return idx

    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
            source = md_file.stem
            chunks = split_into_chunks(text, source)
            idx.chunks.extend(chunks)
            idx.source_files.append(md_file.name)
            logger.debug(f"[RAG] Loaded {len(chunks)} chunks from {md_file.name}")
        except Exception as e:
            logger.warning(f"[RAG] Failed to load {md_file}: {e}")

    # Build document frequency map
    for chunk in idx.chunks:
        for term in set(chunk.tokens):  # unique terms per chunk
            idx.doc_freq[term] = idx.doc_freq.get(term, 0) + 1

    # Average chunk length (in tokens)
    if idx.chunks:
        idx.avg_chunk_len = sum(len(c.tokens) for c in idx.chunks) / len(idx.chunks)

    idx.is_loaded = True
    logger.info(
        f"[RAG] Index built: {len(idx.chunks)} chunks from "
        f"{len(idx.source_files)} files, {len(idx.doc_freq)} unique terms"
    )
    return idx


def get_or_build_index() -> KnowledgeIndex:
    """Return the global index, building it if not yet loaded."""
    global _index
    if not _index.is_loaded:
        _index = build_index()
    return _index


# ── BM25 Scoring ──────────────────────────────────────────────────────────────

def bm25_score(query_tokens: list[str], chunk: Chunk, idx: KnowledgeIndex) -> float:
    """
    BM25 relevance score for a chunk given query tokens.
    Higher is more relevant.
    """
    if not idx.chunks or idx.avg_chunk_len == 0:
        return 0.0

    score = 0.0
    n = len(idx.chunks)
    chunk_len = len(chunk.tokens)
    term_freq = Counter(chunk.tokens)

    for term in query_tokens:
        tf = term_freq.get(term, 0)
        if tf == 0:
            continue
        df = idx.doc_freq.get(term, 0)
        if df == 0:
            continue
        # IDF with smoothing
        idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
        # TF normalised by chunk length
        tf_norm = (tf * (BM25_K1 + 1)) / (
            tf + BM25_K1 * (1 - BM25_B + BM25_B * chunk_len / idx.avg_chunk_len)
        )
        score += idf * tf_norm

    return score


# ── Public Retrieval API ──────────────────────────────────────────────────────

async def retrieve(query: str, top_k: int = TOP_K_DEFAULT) -> list[Chunk]:
    """
    Retrieve the top_k most relevant knowledge chunks for a query.

    Args:
        query: Natural language question or search string
        top_k: Maximum number of chunks to return

    Returns:
        List of Chunk objects sorted by relevance score (highest first).
        Empty list if knowledge base is empty or query has no useful terms.
    """
    idx = get_or_build_index()

    if not idx.chunks:
        logger.debug("[RAG] No chunks in index — returning empty")
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Score all chunks
    scored = []
    for chunk in idx.chunks:
        score = bm25_score(query_tokens, chunk, idx)
        if score > 0:
            scored.append((score, chunk))

    # Sort by score descending, deduplicate by source (max 2 per file)
    scored.sort(key=lambda x: -x[0])

    results = []
    source_count: dict[str, int] = {}
    for score, chunk in scored:
        count = source_count.get(chunk.source, 0)
        if count >= 2:  # max 2 chunks per source document
            continue
        chunk.score = round(score, 3)
        results.append(chunk)
        source_count[chunk.source] = count + 1
        if len(results) >= top_k:
            break

    logger.debug(
        f"[RAG] Query='{query[:60]}' tokens={query_tokens[:5]} "
        f"hits={len(results)}/{len(idx.chunks)}"
    )
    return results


def get_index_status() -> dict:
    """Return index metadata for the /ai/status endpoint."""
    idx = get_or_build_index()
    return {
        "is_loaded": idx.is_loaded,
        "chunk_count": len(idx.chunks),
        "source_files": idx.source_files,
        "unique_terms": len(idx.doc_freq),
        "avg_chunk_length_tokens": round(idx.avg_chunk_len, 1),
        "knowledge_dir": str(KNOWLEDGE_DIR),
        "knowledge_dir_exists": KNOWLEDGE_DIR.exists(),
        "retrieval_algorithm": "BM25",
        "note": "Phase D. Vector-based retrieval can replace retrieve() as a drop-in upgrade.",
    }


def reload_index() -> dict:
    """Force reload the index. Useful after adding new knowledge files."""
    global _index
    _index = KnowledgeIndex()  # reset
    _index = build_index()
    return get_index_status()
