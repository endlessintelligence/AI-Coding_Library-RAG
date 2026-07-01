import os, uuid
import chromadb
from chromadb.config import Settings

PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vector_store")
COLLECTION_NAME = "library_kb"

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=PERSIST_DIR, settings=Settings(anonymized_telemetry=False))
    return _client

def get_or_create_collection():
    client = _get_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except:
        return client.create_collection(COLLECTION_NAME)

def add_chunks(chunks: list[dict], embeddings: list[list[float]]):
    collection = get_or_create_collection()
    ids = [c["id"] for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [{"source": c.get("source", "")} for c in chunks]
    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

def search(query_embedding: list[float], top_k=5) -> list[dict]:
    collection = get_or_create_collection()
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    if not results["documents"]:
        return []
    docs, metas, dists = results["documents"][0], results["metadatas"][0], results["distances"][0]
    return [{"content": d, "source": m.get("source", ""), "score": 1 - dists[i]} for i, (d, m) in enumerate(zip(docs, metas))]

def count() -> int:
    collection = get_or_create_collection()
    return collection.count()

def reset():
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except:
        pass
