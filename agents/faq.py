from model import get_chat_service
from rag.retriever import retrieve, format_context
from . import FAQ_SYSTEM_PROMPT

def run(question: str) -> str:
    results = retrieve(question, top_k=5)
    context = format_context(results) if results else "暂无相关知识库内容"
    prompt = FAQ_SYSTEM_PROMPT + f"\n\n===== 参考知识库内容 =====\n{context}\n\n请基于上述参考内容回答用户的问题。如果参考内容不足以回答，请结合你的知识合理回答。\n回答末尾标注：'回答由模型生成，具体请以实际情况为准。'"
    chat = get_chat_service()
    result = chat.chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return result.strip()
