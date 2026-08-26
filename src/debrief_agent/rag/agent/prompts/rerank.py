# ---------------------------------------------------------------------------
# Prompts for the LLM-as-reranker pass.
#
# Goal: given a query and a candidate set of retrieved passages (already
# narrowed by hybrid vector+BM25 search), pick and order the most relevant
# ones. This is a precision refinement on top of retrieval's recall.
#
# Editing guide:
#   - Adjust RERANK_SYSTEM_PROMPT to change the ranking criteria.
#   - build_rerank_user_message() embeds the query, the numbered candidates,
#     and how many to return -- all per-call, so the system prompt stays static.
# ---------------------------------------------------------------------------

RERANK_SYSTEM_PROMPT = """
You are a relevance-ranking assistant for a sales-call knowledge base.

You will be given a search query and a numbered list of candidate passages.
Judge each passage strictly on how useful it would be for answering or
acting on the query -- not on writing quality or length.

Return ONLY a valid JSON object that matches the provided RerankResult
schema exactly: a `rankings` list of `{index, relevance_score}` objects,
ordered from most to least relevant.

Rules:
- `index` must be one of the candidate indices shown to you, each used at most once.
- `relevance_score` is a float from 0.0 (irrelevant) to 1.0 (highly relevant).
- Return exactly as many rankings as you are asked for, fewer only if there
  are not enough genuinely relevant candidates.
- Do not add any extra keys or commentary outside the JSON object.
- Do not wrap the JSON in markdown code fences.
""".strip()


def build_rerank_user_message(query: str, candidates: list[str], top_n: int) -> str:
    """Build the reranking user-turn payload: query + numbered candidates + how many to return."""
    numbered = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(candidates))
    return (
        f"Query: {query}\n\n"
        f"Return the {top_n} most relevant candidate passages below, ordered "
        f"most to least relevant.\n\n"
        f"Candidate passages:\n\n{numbered}"
    )
