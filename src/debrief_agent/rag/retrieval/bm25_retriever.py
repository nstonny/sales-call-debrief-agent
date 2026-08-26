import re

from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Record
from rank_bm25 import BM25Okapi

from debrief_agent.rag.retrieval.retrieval_models import (
    KnowledgeType,
    RetrievalResult,
    RetrievedChunk,
)
from debrief_agent.rag.retrieval.vector_retriever import VectorRetriever
from debrief_agent.rag.vectorstore.qdrant_store import qdrant_store_service

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class _KnowledgeTypeIndex:
    """A BM25 index over one knowledge type's chunks, plus the chunks it was built from."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        tokenized_chunks = [_tokenize(chunk.text) for chunk in chunks]
        self.token_sets = [set(tokens) for tokens in tokenized_chunks]
        self.bm25 = BM25Okapi(tokenized_chunks) if chunks else None


class BM25Retriever:
    """Lexical (keyword) search over the same chunks the vector store holds.

    Indexes are built lazily per knowledge type and cached for the process
    lifetime -- re-seeding the knowledge base requires a process restart to be
    picked up here, same as every other in-memory client in this service.
    """

    def __init__(self) -> None:
        self._indexes: dict[KnowledgeType, _KnowledgeTypeIndex] = {}

    def retrieve(self, query: str, knowledge_type: KnowledgeType, limit: int) -> RetrievalResult:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty")

        index = self._get_index(knowledge_type)
        if index.bm25 is None:
            return RetrievalResult(query=cleaned_query, chunks=[])

        query_tokens = _tokenize(cleaned_query)
        query_term_set = set(query_tokens)
        scores = index.bm25.get_scores(query_tokens)
        ranked = sorted(
            zip(index.chunks, index.token_sets, scores, strict=True),
            key=lambda triple: triple[2],
            reverse=True,
        )
        # BM25's idf term can be exactly zero (or, before smoothing, negative)
        # for a query term that appears in a large share of a small corpus, so
        # a real match can still score <= 0. Filter on actual token overlap
        # instead of on the score's sign.
        top_chunks = [
            chunk.model_copy(update={"score": float(score)})
            for chunk, token_set, score in ranked[:limit]
            if query_term_set & token_set
        ]
        return RetrievalResult(query=cleaned_query, chunks=top_chunks)

    def _get_index(self, knowledge_type: KnowledgeType) -> _KnowledgeTypeIndex:
        if knowledge_type not in self._indexes:
            self._indexes[knowledge_type] = self._build_index(knowledge_type)
        return self._indexes[knowledge_type]

    def _build_index(self, knowledge_type: KnowledgeType) -> _KnowledgeTypeIndex:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.category", match=MatchValue(value=knowledge_type.value)
                )
            ]
        )
        records = qdrant_store_service.scroll_all(query_filter=query_filter)
        chunks = [self._record_to_chunk(record, knowledge_type) for record in records]
        return _KnowledgeTypeIndex([chunk for chunk in chunks if chunk.text])

    @staticmethod
    def _record_to_chunk(record: Record, knowledge_type: KnowledgeType) -> RetrievedChunk:
        payload = record.payload if isinstance(record.payload, dict) else {}
        metadata_raw = payload.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        return RetrievedChunk(
            text=VectorRetriever._resolve_text(payload=payload, metadata=metadata),
            score=0.0,
            source=VectorRetriever._resolve_source(payload=payload, metadata=metadata),
            knowledge_type=knowledge_type,
            metadata=metadata,
        )


bm25_retriever = BM25Retriever()
