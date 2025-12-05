# backend/api/users.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db import crud
from ..db.models import SubscriptionTier
from ..utils.auth import hash_password, verify_password
from ..utils.jwt_deps import get_current_user_id_dep

router = APIRouter(prefix="/users", tags=["users"])

# Pydantic models for request/response
class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    role: str
    subscriptionTier: str
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None  # Changed from EmailStr to str to allow empty strings, validation happens in crud
    subscriptionTier: Optional[str] = None
    
    class Config:
        # Allow empty strings to be converted to None
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "subscriptionTier": "user"
            }
        }

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")

class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str
    user: UserResponse

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    name: Optional[str] = None

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get current user profile.
    PHASE 4: JWT-only authentication.
    """
    user = crud.get_user_by_id(db, user_id)
    
    if not user:
        # Try to create a default user if doesn't exist (for testing)
        # But first check if email already exists to avoid duplicates
        email = f"user_{user_id}@example.com"
        existing_user = crud.get_user_by_email(db, email)
        if existing_user:
            # Use the existing user instead
            user = existing_user
        else:
            try:
                user = crud.create_user(
                    db,
                    email=email,
                    name="Test User",
                    subscription_tier=SubscriptionTier.USER
                )
            except Exception as e:
                # If creation fails (e.g., duplicate), try to get by email again
                user = crud.get_user_by_email(db, email)
                if not user:
                    raise HTTPException(status_code=500, detail=f"Failed to create or find user: {str(e)}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        subscriptionTier=user.subscription_tier.value,
        createdAt=user.created_at.isoformat(),
        updatedAt=user.updated_at.isoformat(),
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    update_data: UpdateUserRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Update current user profile.
    PHASE 4: JWT-only authentication.
    """
    user = crud.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Convert subscription tier string to enum if provided
    subscription_tier = None
    if update_data.subscriptionTier:
        try:
            subscription_tier = SubscriptionTier(update_data.subscriptionTier.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid subscription tier: {update_data.subscriptionTier}"
            )
    
    try:
        # Normalize empty strings to None (frontend might send empty strings)
        name_value = update_data.name if update_data.name and update_data.name.strip() else None
        email_value = update_data.email if update_data.email and update_data.email.strip() else None
        
        updated_user = crud.update_user(
            db,
            user_id,
            name=name_value,
            email=email_value,
            subscription_tier=subscription_tier
        )
        
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found or update failed")
        
        # crud.update_user already commits, so we just need to refresh
        db.refresh(updated_user)
        
    except ValueError as e:
        # Handle validation errors (e.g., invalid email)
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")
    
    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        name=updated_user.name,
        role=updated_user.role.value,
        subscriptionTier=updated_user.subscription_tier.value,
        createdAt=updated_user.created_at.isoformat(),
        updatedAt=updated_user.updated_at.isoformat(),
    )

@router.get("/check-email")
def check_user_exists(
    email: str = Query(..., description="Email address to check"),
    db: Session = Depends(get_db)
):
    """
    Check if a user exists by email.
    Returns isNewUser: true if user doesn't exist (new user), false if exists (returning user).
    If user exists, also returns the user data.
    """
    user = crud.get_user_by_email(db, email)
    if user:
        return {
            "exists": True,
            "isNewUser": False,
            "user": UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role.value,
                subscriptionTier=user.subscription_tier.value,
                createdAt=user.created_at.isoformat(),
                updatedAt=user.updated_at.isoformat(),
            ).dict()
        }
    return {"exists": False, "isNewUser": True}

@router.get("/by-email")
def get_user_by_email_endpoint(
    email: str = Query(..., description="Email address"),
    db: Session = Depends(get_db)
):
    """
    Get user by email address.
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        subscriptionTier=user.subscription_tier.value,
        createdAt=user.created_at.isoformat(),
        updatedAt=user.updated_at.isoformat(),
    )

@router.post("/login", response_model=LoginResponse)
def login(
    login_data: LoginRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    Returns JWT token and user data if credentials are valid.
    """
    from ..services.jwt_service import jwt_service
    
    user = crud.get_user_by_email(db, login_data.email)
    
    if not user:
        # Don't reveal if user exists or not (security best practice)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not user.password_hash:
        # User exists but has no password (OAuth user)
        provider = user.auth_provider or "OAuth"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Please sign in using {provider}. This account was created with {provider}."
        )
    
    if not verify_password(login_data.password, user.password_hash):
        # Wrong password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Password is correct - generate JWT token
    token = jwt_service.create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            subscriptionTier=user.subscription_tier.value,
            createdAt=user.created_at.isoformat(),
            updatedAt=user.updated_at.isoformat(),
        ),
    )

class RegisterResponse(BaseModel):
    """Register response with JWT token."""
    access_token: str
    user: UserResponse
    requires_verification: bool  # Whether email verification is needed

@router.post("/register", response_model=RegisterResponse)
def register(
    register_data: RegisterRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and password.
    Enforces email uniqueness - no duplicate accounts allowed.
    Password is hashed before storage - never stored in plain text.
    Sends OTP for email verification.
    """
    from ..services.jwt_service import jwt_service
    from ..services.email_service import email_service
    
    # Normalize email (lowercase, trim)
    normalized_email = register_data.email.lower().strip()
    
    # Check if user already exists (enforce email uniqueness)
    existing = crud.get_user_by_email(db, normalized_email)
    if existing:
        # Check if existing user used OAuth
        if existing.auth_provider and existing.auth_provider != "email":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with this email already exists. Please sign in using {existing.auth_provider}."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please use a different email or log in."
            )
    
    # Hash the password before storing
    password_hash = hash_password(register_data.password)
    
    # Create user with hashed password (email is normalized)
    try:
        user = crud.create_user(
            db,
            email=normalized_email,
            password_hash=password_hash,  # Store hash, never plain text
            name=register_data.name,
            auth_provider="email",
            email_verified=False,  # Will be verified via OTP
            subscription_tier=SubscriptionTier.USER
        )
    except Exception as e:
        # Catch database-level unique constraint violations
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please use a different email or log in."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account: {str(e)}"
        )
    
    # Send verification OTP
    otp_code = email_service.generate_otp()
    crud.create_email_otp(db, normalized_email, otp_code, "verification")
    email_service.send_otp_email(normalized_email, otp_code, "verification")
    
    # Generate JWT token
    token = jwt_service.create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    # Return user data with token
    return RegisterResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            subscriptionTier=user.subscription_tier.value,
            createdAt=user.created_at.isoformat(),
            updatedAt=user.updated_at.isoformat(),
        ),
        requires_verification=True,
    )

@router.post("/", response_model=UserResponse)
def create_user(
    email: EmailStr = Body(...),
    name: Optional[str] = Body(None),
    subscription_tier: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    """
    Create a new user (for testing/registration without password).
    In production, use /register endpoint instead.
    """
    # Check if user already exists
    existing = crud.get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    tier = SubscriptionTier.USER
    if subscription_tier:
        try:
            tier = SubscriptionTier(subscription_tier.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid subscription tier: {subscription_tier}")
    
    # Create user without password (for OAuth or testing)
    user = crud.create_user(db, email=email, password_hash=None, name=name, subscription_tier=tier)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        subscriptionTier=user.subscription_tier.value,
        createdAt=user.created_at.isoformat(),
        updatedAt=user.updated_at.isoformat(),
    )

