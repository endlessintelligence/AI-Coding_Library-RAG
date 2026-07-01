# api/session.py - 对话会话管理（内存存储，用于多轮对话历史）

import time, uuid

MAX_HISTORY = 10
SESSION_TTL = 1800
_sessions = {}


def create_session() -> str:
    sid = uuid.uuid4().hex[:12]
    _sessions[sid] = {"messages": [], "updated_at": time.time()}
    return sid


def get_history(session_id: str) -> list:
    if session_id not in _sessions:
        _sessions[session_id] = {"messages": [], "updated_at": time.time()}
    return _sessions[session_id]["messages"]


def add_message(session_id: str, role: str, content: str):
    if session_id not in _sessions:
        _sessions[session_id] = {"messages": [], "updated_at": time.time()}
    s = _sessions[session_id]
    s["messages"].append({"role": role, "content": content})
    if len(s["messages"]) > MAX_HISTORY * 2:
        s["messages"] = s["messages"][-MAX_HISTORY * 2:]
    s["updated_at"] = time.time()
    _cleanup()


def _cleanup():
    now = time.time()
    expired = [sid for sid, s in _sessions.items()
               if now - s["updated_at"] > SESSION_TTL]
    for sid in expired:
        del _sessions[sid]
