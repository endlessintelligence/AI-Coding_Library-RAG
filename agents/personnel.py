# agents/personnel.py - 人员管理助手（管理员值班/志愿/活动人员，可扩展全馆人员管理）

from model import get_chat_service
from . import PERSONNEL_SYSTEM_PROMPT


def run(question: str) -> str:
    chat = get_chat_service()
    result = chat.chat(
        messages=[
            {"role": "system", "content": PERSONNEL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return result.strip()
