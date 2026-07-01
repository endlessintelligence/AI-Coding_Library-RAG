from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str, chunk_size=300, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " "],
    )
    return splitter.split_text(text)

def chunk_documents(docs: list[dict]) -> list[dict]:
    chunks = []
    for doc in docs:
        parts = chunk_text(doc["content"])
        for i, part in enumerate(parts):
            chunks.append({"id": f"{doc['id']}_{i}", "content": part, "source": doc.get("source", "")})
    return chunks
