# agents/resources.py - 资源助手（座位分布/图书分类位置/设备信息，可扩展全部图书馆资源）

from model import get_chat_service
from . import RESOURCES_SYSTEM_PROMPT


def run(question: str) -> str:
    chat = get_chat_service()
    result = chat.chat(
        messages=[
            {"role": "system", "content": RESOURCES_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    return result.strip()
