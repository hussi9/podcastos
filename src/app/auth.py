"""
Authentication Service for PodcastOS.

Uses Supabase Auth for:
- Email/password signup and login
- Session management
- Password reset
"""

import os
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)


# ============== Models ==============

class SignUpRequest(BaseModel):
    """User signup request."""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class AuthUser(BaseModel):
    """Authenticated user."""
    id: str
    email: str
    full_name: Optional[str] = None
    access_token: str
    refresh_token: str


class AuthResult(BaseModel):
    """Authentication result."""
    success: bool
    user: Optional[AuthUser] = None
    error: Optional[str] = None


# ============== Auth Service ==============

class AuthNotConfiguredError(Exception):
    """Raised when authentication service is not properly configured."""
    pass


class AuthService:
    """
    Authentication service using Supabase Auth.
    
    Provides graceful degradation when Supabase is not configured.
    """
    
    _instance = None
    _initialized = False
    _available = False
    _error_message = None

    def __init__(self, raise_on_error: bool = False):
        """
        Initialize auth service.
        
        Args:
            raise_on_error: If True, raise exception when not configured.
                           If False, service will be in degraded mode.
        """
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")  # Use anon key for auth
        
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_ANON_KEY")
        
        if missing:
            self._error_message = f"Missing environment variables: {', '.join(missing)}"
            self._available = False
            self.client = None
            
            if raise_on_error:
                raise AuthNotConfiguredError(
                    f"{self._error_message}. "
                    "Please set these environment variables to enable authentication.\n"
                    "Get your credentials at: https://supabase.com/dashboard"
                )
            else:
                logger.warning(
                    f"⚠️  Auth service running in DEMO MODE: {self._error_message}. "
                    "Authentication features will be disabled."
                )
                return
        
        try:
            self.client: Client = create_client(url, key)
            self._available = True
            self._error_message = None
            logger.info("✅ Auth service initialized successfully")
        except Exception as e:
            self._error_message = f"Failed to initialize Supabase client: {e}"
            self._available = False
            self.client = None
            
            if raise_on_error:
                raise AuthNotConfiguredError(self._error_message)
            else:
                logger.warning(f"⚠️  Auth service in DEMO MODE: {self._error_message}")
    
    @property
    def is_available(self) -> bool:
        """Check if authentication service is available."""
        return self._available
    
    @property
    def error_message(self) -> Optional[str]:
        """Get error message if service is not available."""
        return self._error_message
    
    def _check_available(self) -> bool:
        """Check if service is available, log warning if not."""
        if not self._available:
            logger.warning("Auth operation attempted but service is not configured")
            return False
        return True

    async def sign_up(self, request: SignUpRequest) -> AuthResult:
        """
        Sign up a new user.

        Args:
            request: Signup request with email, password, and optional name

        Returns:
            AuthResult with user info or error
        """
        if not self._check_available():
            return AuthResult(
                success=False,
                error="Authentication service is not configured. Please contact support."
            )
        
        try:
            # Sign up with Supabase Auth
            response = self.client.auth.sign_up({
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": {
                        "full_name": request.full_name,
                    }
                }
            })

            if response.user:
                # Create user profile in our database
                await self._create_profile(
                    user_id=response.user.id,
                    email=request.email,
                    full_name=request.full_name,
                )

                return AuthResult(
                    success=True,
                    user=AuthUser(
                        id=response.user.id,
                        email=response.user.email,
                        full_name=request.full_name,
                        access_token=response.session.access_token if response.session else "",
                        refresh_token=response.session.refresh_token if response.session else "",
                    )
                )
            else:
                return AuthResult(success=False, error="Signup failed")

        except Exception as e:
            logger.error(f"Signup error: {e}")
            return AuthResult(success=False, error=str(e))

    async def login(self, request: LoginRequest) -> AuthResult:
        """
        Log in an existing user.

        Args:
            request: Login request with email and password

        Returns:
            AuthResult with user info and tokens or error
        """
        if not self._check_available():
            return AuthResult(
                success=False,
                error="Authentication service is not configured. Please contact support."
            )
        
        try:
            response = self.client.auth.sign_in_with_password({
                "email": request.email,
                "password": request.password,
            })

            if response.user and response.session:
                return AuthResult(
                    success=True,
                    user=AuthUser(
                        id=response.user.id,
                        email=response.user.email,
                        full_name=response.user.user_metadata.get("full_name"),
                        access_token=response.session.access_token,
                        refresh_token=response.session.refresh_token,
                    )
                )
            else:
                return AuthResult(success=False, error="Login failed")

        except Exception as e:
            logger.error(f"Login error: {e}")
            error_msg = str(e)
            if "Invalid login" in error_msg:
                error_msg = "Invalid email or password"
            return AuthResult(success=False, error=error_msg)

    async def logout(self, access_token: str) -> bool:
        """Log out user by invalidating their session."""
        try:
            self.client.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

    async def get_user(self, access_token: str) -> Optional[AuthUser]:
        """
        Get current user from access token.

        Args:
            access_token: JWT access token

        Returns:
            AuthUser if valid, None otherwise
        """
        try:
            # Set the session with the access token
            response = self.client.auth.get_user(access_token)

            if response.user:
                return AuthUser(
                    id=response.user.id,
                    email=response.user.email,
                    full_name=response.user.user_metadata.get("full_name"),
                    access_token=access_token,
                    refresh_token="",
                )
        except Exception as e:
            logger.error(f"Get user error: {e}")

        return None

    async def refresh_session(self, refresh_token: str) -> Optional[AuthUser]:
        """
        Refresh an expired session.

        Args:
            refresh_token: Refresh token from previous login

        Returns:
            AuthUser with new tokens or None
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)

            if response.user and response.session:
                return AuthUser(
                    id=response.user.id,
                    email=response.user.email,
                    full_name=response.user.user_metadata.get("full_name"),
                    access_token=response.session.access_token,
                    refresh_token=response.session.refresh_token,
                )
        except Exception as e:
            logger.error(f"Refresh session error: {e}")

        return None

    async def reset_password(self, email: str) -> bool:
        """
        Send password reset email.

        Args:
            email: User's email address

        Returns:
            True if email sent, False otherwise
        """
        try:
            self.client.auth.reset_password_email(email)
            return True
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return False

    async def _create_profile(self, user_id: str, email: str, full_name: Optional[str] = None):
        """Create user profile in database."""
        try:
            # Use service key for profile creation
            service_key = os.getenv("SUPABASE_SERVICE_KEY")
            url = os.getenv("SUPABASE_URL")
            admin_client = create_client(url, service_key)

            # Check if profile already exists
            existing = admin_client.table("profiles").select("id").eq("id", user_id).execute()

            if not existing.data:
                # Create new profile
                admin_client.table("profiles").insert({
                    "id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "created_at": datetime.now().isoformat(),
                }).execute()
                logger.info(f"Created profile for user {user_id}")

        except Exception as e:
            logger.error(f"Create profile error: {e}")


# ============== FastAPI Dependencies ==============

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[AuthUser]:
    """
    FastAPI dependency to get current authenticated user.

    Usage:
        @app.get("/protected")
        async def protected_route(user: AuthUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if not credentials:
        return None

    auth_service = AuthService()
    user = await auth_service.get_user(credentials.credentials)
    return user


async def require_auth(
    user: Optional[AuthUser] = Depends(get_current_user)
) -> AuthUser:
    """
    FastAPI dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# Convenience instance
auth = AuthService()
