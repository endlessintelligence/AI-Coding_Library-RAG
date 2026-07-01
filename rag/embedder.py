import os, time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None
_embedding_model = None

def _get_client():
    global _client, _embedding_model
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("MODEL_API_KEY"),
            base_url=os.getenv("EMBEDDING_BASE_URL") or os.getenv("MODEL_BASE_URL"),
        )
        _embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v2")
    return _client, _embedding_model

def embed_text(text: str) -> list[float]:
    client, model = _get_client()
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding

def embed_batch(texts: list[str], batch_size=16) -> list[list[float]]:
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        client, model = _get_client()
        for attempt in range(3):
            try:
                resp = client.embeddings.create(model=model, input=batch)
                results.extend([d.embedding for d in resp.data])
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(1)
                else:
                    raise e
    return results
