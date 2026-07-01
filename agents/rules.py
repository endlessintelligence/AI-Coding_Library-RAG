# agents/rules.py - 规则助手（预约/签到/暂离/违规规则，可扩展借还/设备规则）

from model import get_chat_service
from . import RULES_SYSTEM_PROMPT


def run(question: str) -> str:
    chat = get_chat_service()
    result = chat.chat(
        messages=[
            {"role": "system", "content": RULES_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    return result.strip()
