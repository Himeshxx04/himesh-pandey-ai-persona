"""
FAISS retriever — returns top-k chunks with source metadata.
Lazy-loads the index on first use so import is fast.
"""

from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass

from langchain_community.vectorstores import FAISS


@dataclass
class RetrievedChunk:
    text: str
    source: str        # e.g. "resume", "about_me", "github:rag-pipeline-optimizer"
    score: float       # cosine similarity (higher = more relevant)


class Retriever:
    def __init__(self, store: FAISS, top_k: int = 5, score_threshold: float = 0.25):
        self._store = store
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(self, query: str) -> List[RetrievedChunk]:
        """Return top-k chunks above score_threshold, sorted by relevance."""
        results: List[Tuple] = self._store.similarity_search_with_relevance_scores(
            query, k=self.top_k
        )
        chunks = []
        for doc, score in results:
            if score < self.score_threshold:
                continue
            chunks.append(RetrievedChunk(
                text=doc.page_content.strip(),
                source=doc.metadata.get("source", "unknown"),
                score=round(score, 4),
            ))
        return chunks

    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        """Format retrieved chunks into a context block for the LLM prompt."""
        if not chunks:
            return ""
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] ({c.source})\n{c.text}")
        return "\n\n---\n\n".join(parts)
