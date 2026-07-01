# agents/master.py - Master Agent（LLM 意图分类路由：RULES/RESOURCES/PERSONNEL/FAQ）

from model import get_chat_service
from . import MASTER_SYSTEM_PROMPT


def run(question: str) -> tuple:
    chat = get_chat_service()
    result = chat.chat(
        messages=[
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=100,
    )
    decision = result.strip().upper()
    for route in ["RULES", "RESOURCES", "PERSONNEL", "FAQ"]:
        if route in decision:
            return route, f"意图识别为: {route}"
    return "FAQ", "未能明确意图，默认使用FAQ检索"
