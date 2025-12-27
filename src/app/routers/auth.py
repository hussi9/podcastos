
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from src.app.auth import AuthService, SignUpRequest, LoginRequest, AuthUser, get_current_user

router = APIRouter()

# --- Schemas ---
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None

class AuthResponse(BaseModel):
    success: bool
    user: Optional[UserResponse] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None

# --- Routes ---

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest):
    """Sign up a new user."""
    auth_service = AuthService()
    result = await auth_service.sign_up(request)

    if result.success and result.user:
        return AuthResponse(
            success=True,
            user=UserResponse(
                id=result.user.id,
                email=result.user.email,
                full_name=result.user.full_name
            ),
            access_token=result.user.access_token,
            refresh_token=result.user.refresh_token
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=result.error or "Signup failed"
        )

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Log in an existing user."""
    auth_service = AuthService()
    result = await auth_service.login(request)

    if result.success and result.user:
        return AuthResponse(
            success=True,
            user=UserResponse(
                id=result.user.id,
                email=result.user.email,
                full_name=result.user.full_name
            ),
            access_token=result.user.access_token,
            refresh_token=result.user.refresh_token
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=result.error or "Login failed"
        )

@router.post("/logout")
async def logout(user: AuthUser = Depends(get_current_user)):
    """Log out current user."""
    if user:
        auth_service = AuthService()
        await auth_service.logout(user.access_token)
    return {"success": True}

@router.get("/me", response_model=AuthResponse)
async def get_me(user: AuthUser = Depends(get_current_user)):
    """Get current authenticated user."""
    if not user:
        return AuthResponse(success=False, error="Not authenticated")

    return AuthResponse(
        success=True,
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name
        )
    )
