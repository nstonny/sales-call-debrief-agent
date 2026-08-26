from debrief_agent.rag.retrieval.bm25_retriever import bm25_retriever
from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
    RetrievalResult,
    RetrievedChunk,
)
from debrief_agent.rag.retrieval.vector_retriever import vector_retriever

# Standard damping constant for Reciprocal Rank Fusion; keeps a single very
# high rank in one list from dominating the merge.
RRF_K = 60

CANDIDATE_POOL_SIZE = 25


class HybridRetriever:
    """Combine dense vector search with BM25 keyword search via Reciprocal Rank Fusion.

    Fusing by rank rather than raw score avoids comparing cosine similarity and
    BM25 scores, which live on unrelated scales.
    """

    def retrieve(
        self,
        query: str,
        knowledge_type: KnowledgeType,
        limit: int,
        candidate_pool: int = CANDIDATE_POOL_SIZE,
    ) -> RetrievalResult:
        vector_result = vector_retriever.retrieve(
            query=query, limit=candidate_pool, knowledge_type=knowledge_type
        )
        bm25_result = bm25_retriever.retrieve(
            query=query, knowledge_type=knowledge_type, limit=candidate_pool
        )
        fused_chunks = self._fuse(vector_result.chunks, bm25_result.chunks)
        return RetrievalResult(query=query, chunks=fused_chunks[:limit])

    @staticmethod
    def _fuse(
        vector_chunks: list[RetrievedChunk],
        bm25_chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        rrf_scores: dict[str, float] = {}
        chunk_by_text: dict[str, RetrievedChunk] = {}

        for ranked_list in (vector_chunks, bm25_chunks):
            for rank, chunk in enumerate(ranked_list, start=1):
                rrf_scores[chunk.text] = rrf_scores.get(chunk.text, 0.0) + 1.0 / (RRF_K + rank)
                chunk_by_text.setdefault(chunk.text, chunk)

        ranked_texts = sorted(rrf_scores, key=lambda text: rrf_scores[text], reverse=True)
        return [
            chunk_by_text[text].model_copy(update={"score": rrf_scores[text]})
            for text in ranked_texts
        ]


hybrid_retriever = HybridRetriever()
