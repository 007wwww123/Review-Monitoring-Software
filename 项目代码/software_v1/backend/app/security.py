from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SysUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _secret() -> str:
    value = os.getenv("JWT_SECRET_KEY")
    if not value:
        raise RuntimeError("JWT_SECRET_KEY is required")
    return value


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user: SysUser) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "30")))
    return jwt.encode({"sub": str(user.id), "username": user.username, "role": user.role, "exp": expires}, _secret(), algorithm="HS256"), expires


def current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)) -> SysUser:
    credentials = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, RuntimeError) as exc:
        raise credentials from exc
    user = db.get(SysUser, user_id)
    if user is None or user.status != "active":
        raise credentials
    return user
