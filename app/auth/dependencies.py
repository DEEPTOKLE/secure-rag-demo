from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt_handler import decode_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency: validate Bearer token and return user claims.

    The returned dict is consumed by get_db() to stamp app.* session variables.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = {
            "user_id": payload["user_id"],
            "role": payload["role"],
            "tenant_id": payload["tenant_id"],
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return claims


def require_role(*allowed_roles: str):
    """Dependency factory: only users whose role is in *allowed_roles* pass."""

    def _checker(
        claims: dict = Depends(get_current_user),
    ) -> dict:
        if claims["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return claims

    return _checker
