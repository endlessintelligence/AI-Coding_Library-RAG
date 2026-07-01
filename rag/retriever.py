from .embedder import embed_text
from .store import search

def retrieve(query: str, top_k=5) -> list[dict]:
    query_vec = embed_text(query)
    return search(query_vec, top_k=top_k)

def format_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results):
        parts.append(f"[{i+1}] {r['content']}")
    return "\n\n".join(parts)
