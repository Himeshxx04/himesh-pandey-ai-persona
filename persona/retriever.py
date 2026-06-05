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
    def __init__(self, store: FAISS, top_k: int = 5, irrelevance_threshold: float = 0.10):
        """
        Args:
            store: FAISS vectorstore
            top_k: always return this many chunks (unless corpus is smaller)
            irrelevance_threshold: if the TOP-1 chunk's cosine score is below this,
                the query is genuinely unrelated to the corpus — return empty list so
                the LLM knows to refuse (injection guard, off-topic questions).
                This is intentionally low (0.10) so normal questions always get context.
        """
        self._store = store
        self.top_k = top_k
        self.irrelevance_threshold = irrelevance_threshold

    def retrieve(self, query: str) -> List[RetrievedChunk]:
        """
        Return top-k chunks. Returns empty list only when the best match is
        below irrelevance_threshold (true off-topic query).

        FAISS returns L2 distances; for unit-normalized vectors:
            cosine_similarity = 1 - (l2_dist ** 2) / 2
        """
        results: List[Tuple] = self._store.similarity_search_with_score(
            query, k=self.top_k
        )
        if not results:
            return []

        chunks = []
        for doc, l2_dist in results:
            cosine_sim = float(1.0 - (l2_dist ** 2) / 2.0)
            cosine_sim = max(0.0, min(1.0, cosine_sim))
            chunks.append(RetrievedChunk(
                text=doc.page_content.strip(),
                source=doc.metadata.get("source", "unknown"),
                score=round(cosine_sim, 4),
            ))

        # Guard: if the very best result is near-zero, query is off-topic
        if chunks[0].score < self.irrelevance_threshold:
            return []

        return chunks

    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        """Format retrieved chunks into a context block for the LLM prompt."""
        if not chunks:
            return ""
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] ({c.source})\n{c.text}")
        return "\n\n---\n\n".join(parts)
