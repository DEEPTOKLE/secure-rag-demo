from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth.jwt_handler import create_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Demo-only user store.  In production this would be a users table.
DEMO_USERS: dict[str, dict] = {
    "alice": {"user_id": 1, "role": "hr_manager", "tenant_id": 1},
    "bob": {"user_id": 2, "role": "finance_manager", "tenant_id": 1},
    "carol": {"user_id": 3, "role": "admin", "tenant_id": 1},
}


class LoginRequest(BaseModel):
    username: str


@router.post("/login")
async def login(payload: LoginRequest):
    username = payload.username
    if username not in DEMO_USERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown demo user",
        )
    user = DEMO_USERS[username]
    token = create_token(user["user_id"], user["role"], user["tenant_id"])
    return {"access_token": token, "token_type": "bearer"}
