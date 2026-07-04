import os, docx
from .chunker import chunk_documents
from .embedder import embed_batch
from .store import add_chunks, reset, count

DOCX_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "图书馆相关内容知识库补充.docx")

def read_docx(path: str) -> list[dict]:
    doc = docx.Document(path)
    sections = []
    current_section = ""
    current_paragraphs = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if text.startswith("第一章") or text.startswith("第二章") or text.startswith("第三章") or text.startswith("第四章"):
            if current_paragraphs:
                sections.append({"id": current_section, "content": "\n".join(current_paragraphs), "source": current_section})
            current_section = text
            current_paragraphs = []
        elif text.startswith("1、") or text.startswith("2、") or text.startswith("3、"):
            if current_paragraphs and current_section:
                sections.append({"id": current_section, "content": "\n".join(current_paragraphs), "source": current_section})
            current_section = text[:20]
            current_paragraphs = [text]
        else:
            current_paragraphs.append(text)
    if current_paragraphs and current_section:
        sections.append({"id": current_section, "content": "\n".join(current_paragraphs), "source": current_section})
    return sections

def ingest(force_rebuild=False):
    if not force_rebuild and count() > 0:
        print(f"[Ingest] 知识库已有 {count()} 条记录，跳过（如需重建请用 force_rebuild=True）")
        return
    if force_rebuild:
        reset()
    print("[Ingest] 读取文档...")
    docs = read_docx(DOCX_PATH)
    print(f"[Ingest] 共 {len(docs)} 个段落")
    print("[Ingest] 分块...")
    chunks = chunk_documents(docs)
    print(f"[Ingest] 共 {len(chunks)} 个块")
    print("[Ingest] 生成向量...")
    texts = [c["content"] for c in chunks]
    embeddings = embed_batch(texts)
    print("[Ingest] 存入 ChromaDB...")
    add_chunks(chunks, embeddings)
    print(f"[Ingest] 完成！知识库共 {count()} 条记录")

if __name__ == "__main__":
    ingest(force_rebuild=True)
