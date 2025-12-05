# backend/services/email_service.py
"""
Email service for sending OTP codes for verification and password reset.
"""
import os
import random
import string
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from dotenv import dotenv_values

# For production, use a real email service (SendGrid, AWS SES, etc.)
# For now, we'll use a simple mock that logs to console
# In production, replace with actual email sending

CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}


class EmailService:
    """Service for sending emails (OTP codes, verification, etc.)"""
    
    def __init__(self):
        # In production, initialize your email service here (SendGrid, AWS SES, etc.)
        self.smtp_enabled = os.getenv("SMTP_ENABLED", "false").lower() == "true"
        self.smtp_host = os.getenv("SMTP_HOST") or cfg.get("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587") or cfg.get("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER") or cfg.get("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD") or cfg.get("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL") or cfg.get("FROM_EMAIL", "noreply@gsin.fin")
    
    def send_otp_email(self, email: str, otp_code: str, purpose: str = "verification") -> bool:
        """
        Send OTP code to user's email.
        
        Args:
            email: Recipient email address
            otp_code: 6-digit OTP code
            purpose: "verification" or "password_reset"
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if purpose == "verification":
                subject = "GSIN - Email Verification Code"
                body = f"""
Hello,

Your email verification code is: {otp_code}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.

Best regards,
GSIN Team
"""
            else:  # password_reset
                subject = "GSIN - Password Reset Code"
                body = f"""
Hello,

Your password reset code is: {otp_code}

This code will expire in 10 minutes.

If you didn't request a password reset, please ignore this email.

Best regards,
GSIN Team
"""
            
            # In production, send actual email here
            if self.smtp_enabled and self.smtp_host:
                # TODO: Implement actual SMTP sending
                # import smtplib
                # from email.mime.text import MIMEText
                # ... send email via SMTP
                print(f"[EMAIL] Would send to {email}: {subject}")
                print(f"[EMAIL] Body: {body}")
                return True
            else:
                # Development mode: just log
                print(f"[EMAIL SERVICE] OTP for {email}: {otp_code} (Purpose: {purpose})")
                print(f"[EMAIL SERVICE] In production, this would be sent via email")
                return True
        except Exception as e:
            print(f"[EMAIL SERVICE] Error sending email: {e}")
            return False
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))


# Global instance
email_service = EmailService()

