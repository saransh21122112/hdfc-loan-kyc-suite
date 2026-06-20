from fastapi import APIRouter, Form, HTTPException, status
from kyc_engine.core.security import create_access_token

router = APIRouter()

# Demo credentials — replace with Active Directory integration for bank deployment
_DEMO_USERS = {
    "demo": "demo123",
    "admin": "hdfc2026",
}


@router.post("/token", summary="Get a JWT access token")
async def login(username: str = Form(...), password: str = Form(...)):
    if _DEMO_USERS.get(username) != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(subject=username)
    return {"access_token": token, "token_type": "bearer"}
