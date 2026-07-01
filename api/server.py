# api/server.py - FastAPI 入口（CORS/中间件/初始数据/路由注册）

import os
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from .routes import router as auth_router
from .seat_routes import router as seat_router
from .websocket import connect, disconnect, broadcast
from db import init_db, seed_initial_data, get_session, User

load_dotenv()

init_db()
seed_initial_data()

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    from scheduler.tasks import start_scheduler
    _scheduler = start_scheduler()
    yield
    if _scheduler:
        _scheduler.shutdown()


app = FastAPI(title="智慧图书馆 - 座位预约管理系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        auth = request.headers.get("Authorization", "")
        request.state.user_payload = None
        if auth and auth.startswith("Bearer "):
            from .auth import verify_token
            request.state.user_payload = verify_token(auth[7:])
    response = await call_next(request)
    return response


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    static_file = static_dir / "index.html"
    if static_file.exists():
        return FileResponse(str(static_file))
    return {"message": "智慧图书馆座位预约系统 API 运行中"}


app.include_router(auth_router)
app.include_router(seat_router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        disconnect(ws)


@app.get("/api/ws-status")
def ws_status():
    from .websocket import get_connection_count
    return {"connections": get_connection_count()}


def main():
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload_flag = os.getenv("API_RELOAD", "true").lower() == "true"
    uvicorn.run("api.server:app", host=host, port=port, reload=reload_flag)


if __name__ == "__main__":
    main()
