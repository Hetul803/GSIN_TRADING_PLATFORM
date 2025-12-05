# backend/api/agreements.py
"""
User Agreements API - Terms of Service, Privacy Policy, Risk Disclosure.

Users must accept all agreements before trading.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import UserAgreement

router = APIRouter(prefix="/agreements", tags=["agreements"])


class AgreementResponse(BaseModel):
    agreement_type: str
    agreement_version: str
    accepted: bool
    accepted_at: Optional[datetime]
    content: str  # Full agreement text


class AcceptAgreementRequest(BaseModel):
    agreement_type: str  # "terms", "privacy", "risk_disclosure"
    agreement_version: str


@router.get("/required")
async def get_required_agreements(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
) -> List[AgreementResponse]:
    """
    Get all required agreements for the user.
    Returns agreements with acceptance status.
    """
    # Get user's accepted agreements
    user_agreements = db.query(UserAgreement).filter(
        UserAgreement.user_id == user_id
    ).all()
    
    accepted_map = {
        (ua.agreement_type, ua.agreement_version): ua.accepted
        for ua in user_agreements
    }
    
    # Current agreement versions
    agreements = [
        {
            "type": "terms",
            "version": "1.0",
            "content": get_terms_of_service()
        },
        {
            "type": "privacy",
            "version": "1.0",
            "content": get_privacy_policy()
        },
        {
            "type": "risk_disclosure",
            "version": "1.0",
            "content": get_risk_disclosure()
        }
    ]
    
    responses = []
    for agreement in agreements:
        agreement_type = agreement["type"]
        version = agreement["version"]
        accepted = accepted_map.get((agreement_type, version), False)
        
        # Get acceptance timestamp
        user_agreement = next(
            (ua for ua in user_agreements if ua.agreement_type == agreement_type and ua.agreement_version == version),
            None
        )
        accepted_at = user_agreement.accepted_at if user_agreement and user_agreement.accepted else None
        
        responses.append(AgreementResponse(
            agreement_type=agreement_type,
            agreement_version=version,
            accepted=accepted,
            accepted_at=accepted_at,
            content=agreement["content"]
        ))
    
    return responses


@router.post("/accept")
async def accept_agreement(
    request: AcceptAgreementRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """
    Accept an agreement (Terms, Privacy, Risk Disclosure).
    """
    # Validate agreement type
    valid_types = ["terms", "privacy", "risk_disclosure"]
    if request.agreement_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agreement type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Get or create agreement record
    user_agreement = db.query(UserAgreement).filter(
        UserAgreement.user_id == user_id,
        UserAgreement.agreement_type == request.agreement_type,
        UserAgreement.agreement_version == request.agreement_version
    ).first()
    
    if user_agreement:
        # Update existing
        user_agreement.accepted = True
        user_agreement.accepted_at = datetime.now(timezone.utc)
        if http_request:
            user_agreement.ip_address = http_request.client.host if http_request.client else None
            user_agreement.user_agent = http_request.headers.get("user-agent")
    else:
        # Create new
        import uuid
        user_agreement = UserAgreement(
            id=str(uuid.uuid4()),
            user_id=user_id,
            agreement_type=request.agreement_type,
            agreement_version=request.agreement_version,
            accepted=True,
            accepted_at=datetime.now(timezone.utc),
            ip_address=http_request.client.host if http_request and http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )
        db.add(user_agreement)
    
    db.commit()
    
    return {
        "message": f"Agreement '{request.agreement_type}' accepted",
        "agreement_type": request.agreement_type,
        "agreement_version": request.agreement_version,
        "accepted_at": user_agreement.accepted_at
    }


@router.get("/status")
async def get_agreement_status(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get acceptance status of all required agreements.
    """
    user_agreements = db.query(UserAgreement).filter(
        UserAgreement.user_id == user_id
    ).all()
    
    # Check if all required agreements are accepted
    required = ["terms", "privacy", "risk_disclosure"]
    current_version = "1.0"
    
    accepted = {}
    for agreement_type in required:
        user_agreement = next(
            (ua for ua in user_agreements 
             if ua.agreement_type == agreement_type and ua.agreement_version == current_version),
            None
        )
        accepted[agreement_type] = user_agreement.accepted if user_agreement else False
    
    all_accepted = all(accepted.values())
    
    return {
        "all_accepted": all_accepted,
        "agreements": accepted,
        "can_trade": all_accepted  # Must accept all to trade
    }


def get_terms_of_service() -> str:
    """Get Terms of Service content."""
    return """
# GSIN.TRADE TERMS OF SERVICE

**Last Updated: 2024**

## 1. ACCEPTANCE OF TERMS

By accessing and using GSIN.trade ("Platform", "Service", "we", "us", "our"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, you may not use the Service.

## 2. DESCRIPTION OF SERVICE

GSIN.trade is an algorithmic trading platform that provides:
- Strategy creation and backtesting tools
- Strategy marketplace
- Paper and real trading capabilities
- Strategy evolution and optimization features

## 3. USER ACCOUNTS

3.1. You must be at least 18 years old to use this Service.
3.2. You are responsible for maintaining the confidentiality of your account credentials.
3.3. You are responsible for all activities that occur under your account.
3.4. You must provide accurate and complete information when creating an account.

## 4. TRADING RISKS

4.1. **Trading involves substantial risk of loss.** You may lose all or more than your initial investment.
4.2. Past performance does not guarantee future results.
4.3. Strategies are provided "as-is" without warranty.
4.4. You trade at your own risk and are solely responsible for your trading decisions.
4.5. GSIN.trade is not a registered investment advisor or broker-dealer.

## 5. STRATEGY CREATION AND USE

5.1. Strategies uploaded by users remain the property of the uploader.
5.2. By uploading a strategy, you grant GSIN.trade a license to:
   - Backtest and optimize your strategy
   - Mutate and evolve your strategy (as described in Section 6)
   - Display your strategy in the marketplace (if made public)
5.3. You retain ownership of your original strategy.
5.4. Mutated strategies may become "brain-generated" after significant changes (see Section 6).

## 6. STRATEGY MUTATION AND ROYALTIES

6.1. GSIN.trade may mutate and evolve strategies to improve performance.
6.2. **Royalty Eligibility:**
   - Original uploader receives 5% royalty if strategy similarity > 70% AND mutation count < 3
   - Original uploader receives 2.5% royalty if strategy similarity 50-70% AND mutation count < 3
   - After 3 mutations OR similarity < 50%, strategy becomes "brain-generated" (no royalties to original uploader)
6.3. You can view mutation history and changes in your strategy dashboard.
6.4. Mutation does not affect your ownership of the original strategy.

## 7. PAYMENTS AND FEES

7.1. Subscription fees are charged monthly or annually as selected.
7.2. Platform fees are deducted from strategy creator royalties.
7.3. All fees are non-refundable unless required by law.
7.4. We reserve the right to change pricing with 30 days notice.

## 8. INTELLECTUAL PROPERTY

8.1. The Platform and its content are owned by GSIN.trade.
8.2. User-uploaded strategies remain the property of the user.
8.3. Mutated strategies may be considered derivative works.

## 9. LIMITATION OF LIABILITY

9.1. GSIN.trade is provided "as-is" without warranties of any kind.
9.2. We are not liable for trading losses or damages.
9.3. Our liability is limited to the amount you paid in the last 12 months.
9.4. We are not responsible for broker connection issues or market data delays.

## 10. INDEMNIFICATION

You agree to indemnify and hold GSIN.trade harmless from any claims, damages, or expenses arising from:
- Your use of the Service
- Your trading activities
- Your violation of these Terms
- Your violation of any laws or regulations

## 11. TERMINATION

11.1. We may terminate or suspend your account at any time for violation of these Terms.
11.2. You may cancel your subscription at any time.
11.3. Upon termination, your access to the Service will cease.

## 12. CHANGES TO TERMS

We reserve the right to modify these Terms at any time. Continued use after changes constitutes acceptance.

## 13. GOVERNING LAW

These Terms are governed by the laws of [Your Jurisdiction]. Disputes will be resolved through binding arbitration.

## 14. CONTACT

For questions about these Terms, contact: legal@gsin.trade
"""


def get_privacy_policy() -> str:
    """Get Privacy Policy content."""
    return """
# GSIN.TRADE PRIVACY POLICY

**Last Updated: 2024**

## 1. INFORMATION WE COLLECT

1.1. **Account Information:** Name, email, password (encrypted)
1.2. **Trading Data:** Strategies, trades, performance metrics
1.3. **Payment Information:** Processed securely through Stripe (we don't store full card details)
1.4. **Broker Credentials:** Encrypted API keys (stored securely, never shared)
1.5. **Usage Data:** Logs, IP addresses, device information

## 2. HOW WE USE YOUR INFORMATION

2.1. To provide and improve the Service
2.2. To process payments and royalties
2.3. To communicate with you about your account
2.4. To analyze platform usage and performance
2.5. To comply with legal obligations

## 3. INFORMATION SHARING

3.1. We do not sell your personal information.
3.2. We may share information with:
   - Service providers (Stripe, Alpaca, data hosting)
   - Legal authorities if required by law
   - Business partners (with your consent)
3.3. Public strategies are visible to all users (name and performance only).

## 4. DATA SECURITY

4.1. We use industry-standard encryption for sensitive data.
4.2. Broker API keys are encrypted at rest.
4.3. We implement security measures to protect your data.
4.4. However, no system is 100% secure.

## 5. YOUR RIGHTS

5.1. Access your personal data
5.2. Correct inaccurate data
5.3. Delete your account and data
5.4. Export your data
5.5. Opt-out of marketing communications

## 6. COOKIES AND TRACKING

6.1. We use cookies for authentication and analytics.
6.2. You can disable cookies in your browser settings.

## 7. DATA RETENTION

7.1. We retain your data while your account is active.
7.2. We may retain data for legal or business purposes after account closure.

## 8. CHILDREN'S PRIVACY

Our Service is not intended for users under 18 years old.

## 9. INTERNATIONAL USERS

Your data may be transferred to and processed in countries outside your jurisdiction.

## 10. CHANGES TO PRIVACY POLICY

We may update this Privacy Policy. Continued use constitutes acceptance.

## 11. CONTACT

For privacy questions, contact: privacy@gsin.trade
"""


def get_risk_disclosure() -> str:
    """Get Risk Disclosure content."""
    return """
# GSIN.TRADE RISK DISCLOSURE STATEMENT

**IMPORTANT: READ CAREFULLY BEFORE TRADING**

## 1. TRADING RISKS

**Trading securities, including stocks, options, and other financial instruments, involves substantial risk of loss. You may lose all or more than your initial investment.**

## 2. NO GUARANTEES

2.1. **Past performance does not guarantee future results.**
2.2. Strategy backtests are based on historical data and may not reflect future performance.
2.3. Market conditions change, and strategies that worked in the past may not work in the future.
2.4. There is no guarantee that any strategy will be profitable.

## 3. STRATEGY RISKS

3.1. Strategies are provided "as-is" without warranty.
3.2. Strategies may contain errors or bugs.
3.3. Strategy evolution may not improve performance.
3.4. Strategies may not work in all market conditions.
3.5. You are solely responsible for selecting and using strategies.

## 4. TECHNOLOGY RISKS

4.1. System failures, bugs, or errors may cause losses.
4.2. Market data delays or inaccuracies may affect trading decisions.
4.3. Broker connection issues may prevent order execution.
4.4. Internet connectivity issues may disrupt trading.

## 5. LEVERAGE AND MARGIN RISKS

5.1. Trading on margin amplifies both gains and losses.
5.2. You may be required to deposit additional funds to maintain positions.
5.3. You may lose more than your initial investment.

## 6. MARKET RISKS

6.1. Markets are volatile and unpredictable.
6.2. Prices can move rapidly and dramatically.
6.3. Market gaps may cause significant losses.
6.4. Liquidity issues may prevent order execution at desired prices.

## 7. REGULATORY RISKS

7.1. Trading regulations may change.
7.2. Tax implications vary by jurisdiction.
7.3. You are responsible for compliance with all applicable laws.

## 8. PLATFORM RISKS

8.1. GSIN.trade is not a registered investment advisor or broker-dealer.
8.2. We do not provide investment advice.
8.3. We are not responsible for your trading decisions or losses.
8.4. Platform fees and commissions reduce returns.

## 9. YOUR RESPONSIBILITIES

9.1. You must understand the risks before trading.
9.2. You should only trade with money you can afford to lose.
9.3. You should diversify your investments.
9.4. You should monitor your positions regularly.
9.5. You should consult with a financial advisor if needed.

## 10. ACKNOWLEDGMENT

**By accepting this Risk Disclosure, you acknowledge that:**
- You understand the risks of trading
- You are trading at your own risk
- You are solely responsible for your trading decisions
- You may lose all or more than your initial investment
- GSIN.trade is not liable for your trading losses

## 11. CONTACT

For questions about risks, contact: support@gsin.trade

**DO NOT TRADE UNLESS YOU FULLY UNDERSTAND THE RISKS INVOLVED.**
"""

