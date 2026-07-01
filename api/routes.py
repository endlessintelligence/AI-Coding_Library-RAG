# api/routes.py - 认证路由 + SSE 多智能体问答接口

import json
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from db import get_session, User
from .auth import hash_password, create_token, verify_token
from .session import create_session, get_history, add_message

router = APIRouter()


class RegisterRequest(BaseModel):
    student_id: str
    password: str
    name: str


class LoginRequest(BaseModel):
    student_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    name: str
    is_admin: bool


class ChatRequest(BaseModel):
    question: str
    session_id: str = ""
    user_id: str = ""


def get_current_user(authorization: str = Header("")) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return payload


@router.post("/api/register")
def register(req: RegisterRequest):
    session = get_session()
    try:
        if session.query(User).filter_by(student_id=req.student_id).first():
            raise HTTPException(status_code=400, detail="学号已注册")
        user = User(
            student_id=req.student_id,
            password_hash=hash_password(req.password),
            name=req.name,
        )
        session.add(user)
        session.commit()
        return {"message": "注册成功", "user_id": user.id}
    finally:
        session.close()


@router.post("/api/login", response_model=LoginResponse)
def login(req: LoginRequest):
    session = get_session()
    try:
        user = session.query(User).filter_by(student_id=req.student_id).first()
        if not user or user.password_hash != hash_password(req.password):
            raise HTTPException(status_code=401, detail="学号或密码错误")
        token = create_token({"user_id": user.id, "is_admin": user.is_admin})
        return LoginResponse(token=token, user_id=user.id,
                             name=user.name, is_admin=user.is_admin)
    finally:
        session.close()


@router.get("/api/me")
def get_me(payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        user = session.query(User).get(payload["user_id"])
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"user_id": user.id, "name": user.name,
                "student_id": user.student_id, "is_admin": user.is_admin}
    finally:
        session.close()


@router.post("/api/chat")
def chat(req: ChatRequest):
    from graph.agent import get_graph

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    session_id = req.session_id or create_session()

    def event_stream():
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        initial_state = {
            "user_question": req.question,
            "route_decision": "", "route_reason": "",
            "agent_output": "", "final_answer": "",
        }
        final_answer = ""
        try:
            for event in graph.stream(initial_state, config):
                node_name = list(event.keys())[0]
                state = event[node_name]
                if node_name == "master":
                    yield f"event: route\ndata: {json.dumps({'decision': state.get('route_decision', ''), 'reason': state.get('route_reason', '')})}\n\n"
                elif node_name in ("rules", "resources", "personnel", "faq"):
                    yield f"event: agent_start\ndata: {json.dumps({'agent': node_name})}\n\n"
                    yield f"event: agent_result\ndata: {json.dumps({'agent': node_name, 'output': state.get('agent_output', '')})}\n\n"
                elif node_name == "summarize":
                    final_answer = state.get("final_answer", "") or state.get("agent_output", "")
                    yield f"event: final\ndata: {json.dumps({'answer': final_answer, 'session_id': session_id})}\n\n"
            add_message(session_id, "user", req.question)
            if final_answer:
                add_message(session_id, "assistant", final_answer)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
