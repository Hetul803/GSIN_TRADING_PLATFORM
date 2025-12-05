# backend/api/auth.py
"""
OAuth authentication routes (Google, GitHub, Twitter) and password reset.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from typing import Optional
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db import crud
from ..services.jwt_service import jwt_service
from ..services.email_service import email_service
from ..utils.auth import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


# Request/Response models
class OAuthCallbackRequest(BaseModel):
    """OAuth callback data from provider."""
    provider: str  # "google" (only Google is supported)
    provider_id: str  # Provider's user ID
    email: EmailStr
    name: Optional[str] = None
    access_token: Optional[str] = None  # For future use


class OAuthResponse(BaseModel):
    """OAuth login/register response."""
    access_token: str
    user: dict
    is_new_user: bool


class SendOTPRequest(BaseModel):
    """Request to send OTP for email verification."""
    email: EmailStr
    purpose: str = "verification"  # "verification" or "password_reset"


class VerifyOTPRequest(BaseModel):
    """Request to verify OTP code."""
    email: EmailStr
    otp_code: str
    purpose: str = "verification"


class ResetPasswordRequest(BaseModel):
    """Request to reset password with OTP."""
    email: EmailStr
    otp_code: str
    new_password: str


class SetPasswordRequest(BaseModel):
    """Request to set password after OAuth registration."""
    email: EmailStr
    otp_code: str
    password: str


class ChangePasswordRequest(BaseModel):
    """Request to change password (requires current password)."""
    current_password: str
    new_password: str


@router.post("/oauth/callback", response_model=OAuthResponse)
def oauth_callback(
    oauth_data: OAuthCallbackRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Google.
    Creates user if new, or logs in existing user.
    Returns JWT token.
    
    Note: Only Google OAuth is supported. GitHub and Twitter/X are not supported.
    """
    provider = oauth_data.provider.lower()
    if provider not in ["google"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}. Only Google OAuth is supported."
        )
    
    # Normalize email
    email = oauth_data.email.lower().strip()
    
    # Check if user exists
    user = crud.get_user_by_email(db, email)
    is_new_user = False
    
    if user:
        # Existing user - check if they used this provider before
        if user.auth_provider != provider:
            # User exists but with different auth method
            if user.password_hash:
                # User has password - tell them to use email/password login
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"An account with this email already exists. Please sign in using your email and password, or use {user.auth_provider}."
                )
            else:
                # User has no password but different provider - update provider
                user.auth_provider = provider
                user.provider_id = oauth_data.provider_id
                user.email_verified = True  # OAuth providers verify email
                if oauth_data.name and not user.name:
                    user.name = oauth_data.name
                db.commit()
        else:
            # Same provider - update provider_id if changed
            if user.provider_id != oauth_data.provider_id:
                user.provider_id = oauth_data.provider_id
            if oauth_data.name and not user.name:
                user.name = oauth_data.name
            user.email_verified = True
            db.commit()
    else:
        # New user - create account
        is_new_user = True
        user = crud.create_user(
            db,
            email=email,
            password_hash=None,  # OAuth users don't have passwords
            name=oauth_data.name,
            auth_provider=provider,
            provider_id=oauth_data.provider_id,
            email_verified=True,  # OAuth providers verify email
        )
    
    # Generate JWT token
    token = jwt_service.create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    return OAuthResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "subscriptionTier": user.subscription_tier.value,
        },
        is_new_user=is_new_user,
    )


@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Send OTP code to user's email for verification or password reset.
    """
    email = request.email.lower().strip()
    purpose = request.purpose
    
    if purpose not in ["verification", "password_reset"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purpose must be 'verification' or 'password_reset'"
        )
    
    # For password reset, check if user exists
    if purpose == "password_reset":
        user = crud.get_user_by_email(db, email)
        if not user:
            # Don't reveal if user exists (security)
            return {"message": "If an account exists, an OTP code has been sent."}
        if user.auth_provider and user.auth_provider != "email":
            # User signed up with OAuth - tell them to use OAuth
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Please sign in using {user.auth_provider}."
            )
    
    # Generate OTP
    otp_code = email_service.generate_otp()
    
    # Save OTP to database
    crud.create_email_otp(db, email, otp_code, purpose)
    
    # Send email
    email_service.send_otp_email(email, otp_code, purpose)
    
    return {"message": "OTP code sent to your email."}


@router.post("/verify-otp")
def verify_otp(
    request: VerifyOTPRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Verify OTP code for email verification.
    Returns success status.
    """
    email = request.email.lower().strip()
    otp_code = request.otp_code
    purpose = request.purpose
    
    # Validate OTP
    otp = crud.get_valid_otp(db, email, otp_code, purpose)
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )
    
    # Mark OTP as used
    crud.mark_otp_as_used(db, otp.id)
    
    # If verification, mark user email as verified
    if purpose == "verification":
        user = crud.get_user_by_email(db, email)
        if user:
            user.email_verified = True
            db.commit()
    
    return {"message": "OTP verified successfully.", "verified": True}


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Reset password using OTP code.
    """
    email = request.email.lower().strip()
    otp_code = request.otp_code
    new_password = request.new_password
    
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    
    # Verify OTP
    otp = crud.get_valid_otp(db, email, otp_code, "password_reset")
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )
    
    # Get user
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Check if user has password (not OAuth-only)
    if user.auth_provider and user.auth_provider != "email":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please sign in using {user.auth_provider}."
        )
    
    # Update password
    password_hash = hash_password(new_password)
    user.password_hash = password_hash
    user.email_verified = True  # Password reset implies email verification
    db.commit()
    
    # Mark OTP as used
    crud.mark_otp_as_used(db, otp.id)
    
    return {"message": "Password reset successfully."}


@router.post("/set-password")
def set_password(
    request: SetPasswordRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Set password for OAuth users (optional, for email/password login).
    Requires email verification OTP.
    """
    email = request.email.lower().strip()
    otp_code = request.otp_code
    password = request.password
    
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    
    # Verify OTP
    otp = crud.get_valid_otp(db, email, otp_code, "verification")
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )
    
    # Get user
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Set password
    password_hash = hash_password(password)
    user.password_hash = password_hash
    user.auth_provider = "email"  # Allow email/password login
    user.email_verified = True
    db.commit()
    
    # Mark OTP as used
    crud.mark_otp_as_used(db, otp.id)
    
    return {"message": "Password set successfully."}


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest = Body(...),
    user_id: str = Query(..., description="User ID (from JWT token)"),
    db: Session = Depends(get_db)
):
    """
    Change password for authenticated user (requires current password).
    """
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    
    # Get user
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    # Check if user has password
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set. Please use password reset or OAuth login."
        )
    
    # Verify current password
    from ..utils.auth import verify_password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )
    
    # Update password
    password_hash = hash_password(request.new_password)
    user.password_hash = password_hash
    db.commit()
    
    return {"message": "Password changed successfully."}

