# api/websocket.py - WebSocket 连接管理（实时广播座位状态变化）

from fastapi import WebSocket
from typing import Set

_connections: Set[WebSocket] = set()


async def connect(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)


def disconnect(ws: WebSocket):
    _connections.discard(ws)


async def broadcast(message: dict):
    dead = set()
    for ws in _connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


def get_connection_count() -> int:
    return len(_connections)
