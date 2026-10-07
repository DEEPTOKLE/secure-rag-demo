"""
JWT encode / decode helpers.

Tokens carry three custom claims:
    user_id   – integer (as string for current_setting compatibility)
    role      – 'hr_manager' | 'finance_manager' | 'admin'
    tenant_id – integer (as string)
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET


def create_token(
    user_id: int,
    role: str,
    tenant_id: int,
    secret: str = JWT_SECRET,
    algorithm: str = JWT_ALGORITHM,
    expires_min: int = JWT_EXPIRATION_MINUTES,
) -> str:
    """Encode a JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "role": role,
        "tenant_id": str(tenant_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_min),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str,
    secret: str = JWT_SECRET,
    algorithm: str = JWT_ALGORITHM,
) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, secret, algorithms=[algorithm])
