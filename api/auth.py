# api/auth.py - JWT 认证（注册/登录/令牌签发与验证）

import hmac, hashlib, base64, json, time, os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
SECRET = os.getenv("JWT_SECRET", "dev-secret-key")
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(payload: dict) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload["exp"] = int(time.time()) + EXPIRE_HOURS * 3600
    payload_enc = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    signature = hmac.new(SECRET.encode(),
                         f"{header}.{payload_enc}".encode(),
                         hashlib.sha256).digest()
    sig_enc = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header}.{payload_enc}.{sig_enc}"


def verify_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        expected_sig = hmac.new(SECRET.encode(),
                                f"{parts[0]}.{parts[1]}".encode(),
                                hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(parts[2] + "==")
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
