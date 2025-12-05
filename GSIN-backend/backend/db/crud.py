# backend/db/crud.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func as sql_func
from datetime import datetime, timezone, timedelta
import uuid
import random
import string

# Import all models - these should exist in models.py
from .models import (
    Strategy, Run, Royalty, Memory,
    User, SubscriptionPlan, UserSubscription,
    Group, GroupMember, GroupMessage,
    Trade,
    UserStrategy, StrategyBacktest, StrategyLineage,
    UserTradingSettings, UserPaperAccount,
    EmailOTP, Feedback,
    AdminNotification, UserNotificationRead,
    StrategyRoyalty, UserAgreement,
    UserRole, SubscriptionTier, SubscriptionStatus, GroupRole,
    TradeMode, TradeSide, TradeStatus, TradeSource, AssetType
)

# ---------- Strategies (Legacy) ----------
def upsert_strategy(db: Session, item: Dict[str, Any]) -> None:
    s = db.query(Strategy).filter(Strategy.name == item["name"]).one_or_none()
    if s is None:
        s = Strategy(
            name=item["name"],
            symbol=item["symbol"],
            period=item["period"],
            interval=item["interval"],
            stype=item["strategy"]["type"],
            params=item["strategy"].get("params", {}),
            fees=item.get("fees", {}),
        )
        db.add(s)
    else:
        s.symbol = item["symbol"]
        s.period = item["period"]
        s.interval = item["interval"]
        s.stype = item["strategy"]["type"]
        s.params = item["strategy"].get("params", {})
        s.fees = item.get("fees", {})
    db.commit()

def list_strategies(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(Strategy).order_by(Strategy.id.desc()).all()
    return [
        {
            "name": r.name, "symbol": r.symbol, "period": r.period, "interval": r.interval,
            "strategy": {"type": r.stype, "params": r.params}, "fees": r.fees
        }
        for r in rows
    ]

# ---------- Runs (Legacy) ----------
def create_run(db: Session, m: Dict[str, Any], meta: Dict[str, Any]) -> None:
    r = Run(
        strategy_name=meta.get("strategy", "[adhoc]"),
        symbol=meta.get("symbol", "AAPL"),
        period=meta.get("period", "3mo"),
        interval=meta.get("interval", "1d"),
        stype=meta.get("stype", "sma"),
        params=meta.get("params", {}),
        ret=float(m.get("return", 0.0)),
        sharpe=float(m.get("sharpe", 0.0)),
        dd=float(m.get("dd", 0.0)),
        trades=int(m.get("trades", 0)),
        turnover=float(m.get("turnover", 0.0)),
        regime=m.get("regime", {}),
    )
    db.add(r)
    db.commit()

# ---------- Royalties (Legacy) ----------
def add_royalty(db: Session, strategy_name: str, epoch: str, points: int, total: int) -> None:
    row = Royalty(strategy_name=strategy_name, epoch=str(epoch), points=int(points), total=int(total))
    db.add(row)
    db.commit()

def list_royalties(db: Session, limit: int = 50) -> List[Dict[str, Any]]:
    rows = db.query(Royalty).order_by(Royalty.id.desc()).limit(limit).all()
    return [{"strategy": r.strategy_name, "epoch": r.epoch, "points": r.points, "total": r.total} for r in rows][::-1]

# ---------- Memory (Legacy) ----------
def save_memory(db: Session, vec: List[float], meta: Dict[str, Any], weight: float = 1.0) -> None:
    m = Memory(
        v0=float(vec[0]), v1=float(vec[1]), v2=float(vec[2]), v3=float(vec[3]),
        v4=float(vec[4]), v5=float(vec[5]), v6=float(vec[6]),
        weight=float(weight), meta=meta
    )
    db.add(m)
    db.commit()

def latest_memory_count(db: Session) -> int:
    return db.query(Memory).count()

# ---------- Users ----------
def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()

def create_user(
    db: Session, 
    email: str, 
    password_hash: Optional[str] = None, 
    name: Optional[str] = None, 
    role: UserRole = UserRole.USER, 
    subscription_tier: SubscriptionTier = SubscriptionTier.USER,
    auth_provider: Optional[str] = None,
    provider_id: Optional[str] = None,
    email_verified: bool = False
) -> User:
    """
    Create a new user.
    password_hash should be a bcrypt hash, never plain text.
    For OAuth users, password_hash should be None.
    """
    user = User(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        name=name,
        auth_provider=auth_provider or ("email" if password_hash else None),
        provider_id=provider_id,
        email_verified=email_verified,
        password_hash=password_hash,
        role=role,
        subscription_tier=subscription_tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(
    db: Session, 
    user_id: str, 
    name: Optional[str] = None, 
    email: Optional[str] = None, 
    subscription_tier: Optional[SubscriptionTier] = None
) -> Optional[User]:
    """
    Update user profile.
    
    FIX: Added better error handling and validation.
    """
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return None
        
        # Update fields only if provided (not None)
        # Normalize empty strings to None
        if name is not None:
            user.name = name.strip() if name and name.strip() else None
        if email is not None:
            # Normalize empty strings to None
            if not email or not email.strip():
                # If email is empty, don't update it (keep existing)
                pass
            else:
                # Validate email format - basic check
                email_clean = email.strip().lower()
                if '@' in email_clean:
                    # Check if there's at least one character before @ and after @
                    parts = email_clean.split('@')
                    if len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0:
                        user.email = email_clean
                    else:
                        raise ValueError("Invalid email format")
                else:
                    raise ValueError("Invalid email format")
        if subscription_tier is not None:
            user.subscription_tier = subscription_tier
        
        # Update updated_at timestamp
        from datetime import datetime, timezone
        user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(user)
        return user
    except ValueError:
        # Re-raise validation errors
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in update_user: {e}", exc_info=True)
        raise  # Re-raise to let caller handle

# ---------- Subscriptions ----------
def get_subscription_plan(db: Session, plan_id: str) -> Optional[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

def get_subscription_plan_by_code(db: Session, plan_code: str) -> Optional[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == plan_code).first()

def list_subscription_plans(db: Session, active_only: bool = True) -> List[Dict[str, Any]]:
    query = db.query(SubscriptionPlan)
    if active_only:
        query = query.filter(SubscriptionPlan.is_active == True)
    plans = query.order_by(SubscriptionPlan.price_monthly.asc()).all()
    return [
        {
            "id": p.id,
            "planCode": p.plan_code,
            "name": p.name,
            "priceMonthly": p.price_monthly,
            "defaultRoyaltyPercent": p.default_royalty_percent,
            "platformFeePercent": p.platform_fee_percent,
            "description": p.description,
            "isCreatorPlan": p.is_creator_plan,
            "isActive": p.is_active,
        }
        for p in plans
    ]

def create_subscription_plan(
    db: Session,
    plan_code: str,
    name: str,
    price_monthly: int,
    default_royalty_percent: float,
    description: str,
    is_creator_plan: bool = False,
    platform_fee_percent: Optional[float] = None
) -> SubscriptionPlan:
    # Set platform fee based on plan_code if not provided
    if platform_fee_percent is None:
        if plan_code == "USER":
            platform_fee_percent = 7.0
        elif plan_code == "USER_PLUS_UPLOAD":
            platform_fee_percent = 5.0
        elif plan_code == "CREATOR":
            platform_fee_percent = 3.0
        else:
            platform_fee_percent = 5.0
    
    plan = SubscriptionPlan(
        id=str(uuid.uuid4()),
        plan_code=plan_code,
        name=name,
        price_monthly=price_monthly,
        default_royalty_percent=default_royalty_percent,
        platform_fee_percent=platform_fee_percent,
        performance_fee_percent=default_royalty_percent,  # Legacy compatibility
        description=description,
        is_creator_plan=is_creator_plan,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

def update_subscription_plan(
    db: Session,
    plan_id: str,
    name: Optional[str] = None,
    price_monthly: Optional[int] = None,
    default_royalty_percent: Optional[float] = None,
    platform_fee_percent: Optional[float] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Optional[SubscriptionPlan]:
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        return None
    if name is not None:
        plan.name = name
    if price_monthly is not None:
        plan.price_monthly = price_monthly
    if default_royalty_percent is not None:
        plan.default_royalty_percent = default_royalty_percent
        plan.performance_fee_percent = default_royalty_percent  # Legacy compatibility
    if platform_fee_percent is not None:
        plan.platform_fee_percent = platform_fee_percent
    if description is not None:
        plan.description = description
    if is_active is not None:
        plan.is_active = is_active
    db.commit()
    db.refresh(plan)
    return plan

def get_user_subscription_info(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's subscription info including plan details and permissions."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    plan = None
    if user.current_plan_id:
        plan = get_subscription_plan(db, user.current_plan_id)
    
    # Determine permissions based on plan
    can_upload_strategies = False
    if plan:
        can_upload_strategies = plan.plan_code in ["USER_PLUS_UPLOAD", "CREATOR"]
    
    return {
        "user_id": user.id,
        "plan_id": user.current_plan_id,
        "plan_code": plan.plan_code if plan else "USER",
        "plan_name": plan.name if plan else "User",
        "royalty_percent": user.royalty_percent or (plan.default_royalty_percent if plan else 5.0),
        "can_upload_strategies": can_upload_strategies,
        "is_creator": plan.is_creator_plan if plan else False,
    }

def get_user_active_subscription(db: Session, user_id: str) -> Optional[UserSubscription]:
    """Get user's active subscription."""
    return db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()

def update_user_subscription(
    db: Session, 
    user_id: str, 
    plan_id: str, 
    royalty_percent: Optional[float] = None
) -> Optional[User]:
    """
    Update a user's subscription plan.
    If royalty_percent is None, it will use the plan's default_royalty_percent.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    plan = get_subscription_plan(db, plan_id)
    if not plan:
        return None
    
    user.current_plan_id = plan_id
    user.royalty_percent = royalty_percent if royalty_percent is not None else plan.default_royalty_percent
    user.subscription_tier = SubscriptionTier[plan.plan_code] if plan.plan_code in ["USER", "PRO", "CREATOR"] else SubscriptionTier.USER
    
    db.commit()
    db.refresh(user)
    return user

# ---------- Groups ----------
def create_group(
    db: Session,
    owner_id: str,
    name: str,
    description: Optional[str] = None,
    max_size: Optional[int] = None,
    is_discoverable: bool = False,
    is_paid: bool = False,
    price_monthly: Optional[int] = None
) -> Group:
    """Create a new group with a unique join_code."""
    # Generate unique join code (6-10 alphanumeric characters)
    join_code = None
    while not join_code or db.query(Group).filter(Group.join_code == join_code).first():
        join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    group = Group(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name=name.strip(),
        description=description.strip() if description else None,
        max_size=max_size,
        is_discoverable=is_discoverable,
        is_paid=is_paid,
        price_monthly=price_monthly,
        join_code=join_code,
    )
    db.add(group)
    
    # Create owner membership
    owner_member = GroupMember(
        id=str(uuid.uuid4()),
        group_id=group.id,
        user_id=owner_id,
        role=GroupRole.OWNER,
    )
    db.add(owner_member)
    
    db.commit()
    db.refresh(group)
    return group

def get_group(db: Session, group_id: str) -> Optional[Group]:
    return db.query(Group).filter(Group.id == group_id).first()

def get_group_by_join_code(db: Session, join_code: str) -> Optional[Group]:
    return db.query(Group).filter(Group.join_code == join_code.upper()).first()

def join_group_by_code(db: Session, user_id: str, join_code: str) -> Optional[Group]:
    """Join a group by join_code. Returns the group if successful."""
    group = get_group_by_join_code(db, join_code)
    if not group:
        return None
    
    # Check if already a member
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group.id,
        GroupMember.user_id == user_id
    ).first()
    if existing:
        return group  # Already a member
    
    # Add as member
    member = GroupMember(
        id=str(uuid.uuid4()),
        group_id=group.id,
        user_id=user_id,
        role=GroupRole.MEMBER,
    )
    db.add(member)
    db.commit()
    return group

def count_user_owned_groups(db: Session, user_id: str) -> int:
    """Count groups owned by user."""
    return db.query(Group).filter(Group.owner_id == user_id).count()

def list_user_groups(db: Session, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """List groups user owns and is a member of."""
    owned = db.query(Group).filter(Group.owner_id == user_id).all()
    memberships = db.query(GroupMember).filter(GroupMember.user_id == user_id).all()
    member_group_ids = [m.group_id for m in memberships]
    joined = db.query(Group).filter(Group.id.in_(member_group_ids)).all() if member_group_ids else []
    
    def to_dict(g: Group) -> Dict[str, Any]:
        return {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "owner_id": g.owner_id,
            "join_code": g.join_code,
            "max_size": g.max_size,
            "is_discoverable": g.is_discoverable,
            "is_paid": g.is_paid,
            "price_monthly": g.price_monthly,
            "created_at": g.created_at.isoformat(),
        }
    
    return {
        "owned": [to_dict(g) for g in owned],
        "joined": [to_dict(g) for g in joined if g.owner_id != user_id],  # Exclude owned groups
    }

def get_group_members(db: Session, group_id: str) -> List[Dict[str, Any]]:
    """Get all members of a group."""
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role.value,
            "created_at": m.created_at.isoformat(),
        }
        for m in members
    ]

def delete_group(db: Session, group_id: str, user_id: str) -> bool:
    """Delete a group. Only owner can delete. Returns True if deleted."""
    group = get_group(db, group_id)
    if not group or group.owner_id != user_id:
        return False
    
    db.delete(group)
    db.commit()
    return True

def create_group_message(
    db: Session,
    group_id: str,
    user_id: str,
    encrypted_content: str,
    message_type: str = "TEXT",
    strategy_id: Optional[str] = None
) -> GroupMessage:
    """Create a group message. Supports strategy attachments."""
    message = GroupMessage(
        id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=user_id,
        encrypted_content=encrypted_content,
        message_type=message_type,
        strategy_id=strategy_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

def list_group_messages(
    db: Session,
    group_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[GroupMessage]:
    """List group messages, most recent first."""
    return db.query(GroupMessage).filter(
        GroupMessage.group_id == group_id
    ).order_by(GroupMessage.created_at.desc()).offset(offset).limit(limit).all()

def delete_group_message(db: Session, message_id: str, user_id: str, group_id: str) -> bool:
    """Delete a group message. Owner can delete any, members can delete their own."""
    message = db.query(GroupMessage).filter(GroupMessage.id == message_id).first()
    if not message or message.group_id != group_id:
        return False
    
    # Get group to check ownership
    group = get_group(db, group_id)
    # Check if user is group owner
    is_owner = group and group.owner_id == user_id
    
    # Check if user is message sender
    is_sender = message.user_id == user_id
    
    # Owner can delete any message, but members can't delete owner's messages
    if is_owner:
        db.delete(message)
        db.commit()
        return True
    elif is_sender:
        # Check if message sender is the group owner
        if group and message.user_id == group.owner_id:
            return False  # Members can't delete owner's messages
        db.delete(message)
        db.commit()
        return True
    
    return False

# ---------- Trades ----------
def create_trade(
    db: Session,
    user_id: str,
    symbol: str,
    side: TradeSide,
    quantity: float,
    entry_price: float,
    asset_type: AssetType = AssetType.STOCK,
    mode: TradeMode = TradeMode.PAPER,
    source: TradeSource = TradeSource.MANUAL,
    strategy_id: Optional[str] = None,
    group_id: Optional[str] = None
) -> Trade:
    """Create a new trade."""
    trade = Trade(
        id=str(uuid.uuid4()),
        user_id=user_id,
        symbol=symbol.strip().upper(),
        asset_type=asset_type,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        status=TradeStatus.OPEN,
        mode=mode,
        source=source,
        strategy_id=strategy_id,
        group_id=group_id,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade

def close_trade(
    db: Session, 
    trade_id: str, 
    user_id: str, 
    exit_price: float,
    record_royalty: bool = True  # PHASE 5: Record royalty if profitable
) -> Optional[Trade]:
    """
    Close an open trade and calculate P&L.
    Also calculates and stores royalties for strategy creators (if profit) and performance fees.
    """
    trade = db.query(Trade).filter(
        Trade.id == trade_id,
        Trade.user_id == user_id,
        Trade.status == TradeStatus.OPEN
    ).first()
    
    if not trade:
        return None
    
    trade.exit_price = exit_price
    trade.closed_at = datetime.now(timezone.utc)
    trade.status = TradeStatus.CLOSED
    
    # Calculate P&L
    if trade.side == TradeSide.BUY:
        trade.realized_pnl = (exit_price - trade.entry_price) * trade.quantity
    else:  # SELL
        trade.realized_pnl = (trade.entry_price - exit_price) * trade.quantity
    
    trade.profit = trade.realized_pnl  # Legacy compatibility
    
    # PHASE 5: Calculate royalties using new RoyaltyLedger model
    if record_royalty and trade.realized_pnl and trade.realized_pnl > 0 and trade.strategy_id:
        from ..services.royalty_service import royalty_service
        royalty_entry = royalty_service.record_royalty(trade, db)
        # Royalty is now recorded in RoyaltyLedger table
    
    db.commit()
    db.refresh(trade)
    return trade

def list_user_trades(
    db: Session,
    user_id: str,
    status: Optional[TradeStatus] = None,
    mode: Optional[TradeMode] = None
) -> List[Trade]:
    """List user's trades with optional filters."""
    query = db.query(Trade).filter(Trade.user_id == user_id)
    
    if status:
        query = query.filter(Trade.status == status)
    if mode:
        query = query.filter(Trade.mode == mode)
    
    return query.order_by(Trade.opened_at.desc()).all()

def get_trade_summary(db: Session, user_id: str, mode: Optional[TradeMode] = None) -> Dict[str, Any]:
    """Get trade summary statistics for a user."""
    query = db.query(Trade).filter(Trade.user_id == user_id)
    if mode:
        query = query.filter(Trade.mode == mode)
    
    all_trades = query.all()
    closed_trades = [t for t in all_trades if t.status == TradeStatus.CLOSED and t.realized_pnl is not None]
    open_trades = [t for t in all_trades if t.status == TradeStatus.OPEN]
    
    total_trades = len(all_trades)
    closed_count = len(closed_trades)
    open_count = len(open_trades)
    
    if closed_count > 0:
        wins = len([t for t in closed_trades if t.realized_pnl > 0])
        win_rate = wins / closed_count
        total_pnl = sum(t.realized_pnl for t in closed_trades)
        avg_pnl = total_pnl / closed_count
    else:
        win_rate = 0.0
        total_pnl = 0.0
        avg_pnl = 0.0
    
    return {
        "total_trades": total_trades,
        "open_trades": open_count,
        "closed_trades": closed_count,
        "win_rate": win_rate,
        "total_realized_pnl": total_pnl,
        "avg_realized_pnl": avg_pnl,
    }

# ---------- User Strategies ----------
def create_user_strategy(
    db: Session,
    user_id: str,
    name: str,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    ruleset: Optional[Dict[str, Any]] = None,
    asset_type: AssetType = AssetType.STOCK,
    initial_status: Optional[str] = None  # Optional: override default status
) -> UserStrategy:
    """Create a new user strategy."""
    from .models import UserStrategy
    from ..strategy_engine.status_manager import StrategyStatus
    
    # Determine initial status
    # User uploads should be pending_review, seed strategies should be experiment
    if initial_status:
        status = initial_status
    else:
        # Regular user = pending_review (will be processed by Monitoring Worker)
        status = StrategyStatus.PENDING_REVIEW
    
    strategy = UserStrategy(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        description=description,
        parameters=parameters or {},
        ruleset=ruleset or {},
        asset_type=asset_type,
        is_active=(status != StrategyStatus.PENDING_REVIEW),  # Inactive until reviewed
        status=status,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy

def get_user_strategy(db: Session, strategy_id: str) -> Optional[UserStrategy]:
    return db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()

def list_user_strategies(
    db: Session,
    user_id: str,
    active_only: bool = False,
    ticker: Optional[str] = None,
    min_capital: Optional[float] = None,
    max_capital: Optional[float] = None,
    min_winrate: Optional[float] = None,
    min_sharpe: Optional[float] = None,
    risk_level: Optional[str] = None
) -> List[UserStrategy]:
    """
    List user's strategies with optional filters.
    
    PHASE 2: Added search by ticker, budget, winrate, sharpe, risk level.
    """
    query = db.query(UserStrategy).filter(UserStrategy.user_id == user_id)
    
    if active_only:
        query = query.filter(UserStrategy.is_active == True)
    
    # PHASE 2: Filter by ticker
    if ticker:
        # Check if ticker matches ruleset ticker or ticker field
        query = query.filter(
            or_(
                UserStrategy.ticker.ilike(f"%{ticker}%"),
                UserStrategy.ruleset['ticker'].astext.ilike(f"%{ticker}%")
            )
        )
    
    # PHASE 2: Filter by winrate (from last_backtest_results)
    if min_winrate is not None:
        # Filter strategies where last_backtest_results has win_rate >= min_winrate
        query = query.filter(
            or_(
                UserStrategy.last_backtest_results['win_rate'].astext.cast(sql_func.Float) >= min_winrate,
                UserStrategy.test_metrics['win_rate'].astext.cast(sql_func.Float) >= min_winrate if UserStrategy.test_metrics else False
            )
        )
    
    # PHASE 2: Filter by Sharpe ratio
    if min_sharpe is not None:
        query = query.filter(
            or_(
                UserStrategy.last_backtest_results['sharpe_ratio'].astext.cast(sql_func.Float) >= min_sharpe,
                UserStrategy.test_metrics['sharpe_ratio'].astext.cast(sql_func.Float) >= min_sharpe if UserStrategy.test_metrics else False
            )
        )
    
    # PHASE 2: Filter by risk level (based on max_drawdown or volatility)
    if risk_level:
        # Conservative: max_drawdown < 0.05, Moderate: 0.05-0.15, Aggressive: > 0.15
        if risk_level.lower() == "conservative":
            query = query.filter(
                or_(
                    UserStrategy.last_backtest_results['max_drawdown'].astext.cast(sql_func.Float) < 0.05,
                    UserStrategy.test_metrics['max_drawdown'].astext.cast(sql_func.Float) < 0.05 if UserStrategy.test_metrics else False
                )
            )
        elif risk_level.lower() == "moderate":
            query = query.filter(
                or_(
                    and_(
                        UserStrategy.last_backtest_results['max_drawdown'].astext.cast(sql_func.Float) >= 0.05,
                        UserStrategy.last_backtest_results['max_drawdown'].astext.cast(sql_func.Float) <= 0.15
                    ),
                    and_(
                        UserStrategy.test_metrics['max_drawdown'].astext.cast(sql_func.Float) >= 0.05,
                        UserStrategy.test_metrics['max_drawdown'].astext.cast(sql_func.Float) <= 0.15
                    ) if UserStrategy.test_metrics else False
                )
            )
        elif risk_level.lower() == "aggressive":
            query = query.filter(
                or_(
                    UserStrategy.last_backtest_results['max_drawdown'].astext.cast(sql_func.Float) > 0.15,
                    UserStrategy.test_metrics['max_drawdown'].astext.cast(sql_func.Float) > 0.15 if UserStrategy.test_metrics else False
                )
            )
    
    strategies = query.order_by(UserStrategy.created_at.desc()).all()
    
    # PHASE 2: Filter by capital budget (post-query filtering based on position sizing rules)
    if min_capital is not None or max_capital is not None:
        filtered_strategies = []
        for strategy in strategies:
            # Estimate capital requirement from ruleset or backtest results
            # This is a simplified estimation - could be enhanced
            estimated_capital = 10000.0  # Default
            if strategy.last_backtest_results:
                # Estimate from position size or backtest capital
                estimated_capital = strategy.last_backtest_results.get("initial_capital", 10000.0)
            
            if min_capital is not None and estimated_capital < min_capital:
                continue
            if max_capital is not None and estimated_capital > max_capital:
                continue
            
            filtered_strategies.append(strategy)
        
        return filtered_strategies
    
    return strategies

def update_user_strategy(
    db: Session,
    strategy_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    ruleset: Optional[Dict[str, Any]] = None,
    score: Optional[float] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_proposable: Optional[bool] = None,
    last_backtest_at: Optional[datetime] = None,
    last_backtest_results: Optional[Dict[str, Any]] = None,
    train_metrics: Optional[Dict[str, Any]] = None,
    test_metrics: Optional[Dict[str, Any]] = None,
    evolution_attempts: Optional[int] = None,
    generalized: Optional[bool] = None,
    per_symbol_performance: Optional[Dict[str, Any]] = None,
    explanation_human: Optional[str] = None,  # PHASE 1: Added
    risk_note: Optional[str] = None,  # PHASE 1: Added
) -> Optional[UserStrategy]:
    """Update a user strategy."""
    strategy = get_user_strategy(db, strategy_id)
    if not strategy:
        return None
    
    if name is not None:
        strategy.name = name
    if description is not None:
        strategy.description = description
    if parameters is not None:
        strategy.parameters = parameters
    if ruleset is not None:
        strategy.ruleset = ruleset
    if score is not None:
        strategy.score = score
    if status is not None:
        strategy.status = status
    if is_active is not None:
        strategy.is_active = is_active
    if is_proposable is not None:
        strategy.is_proposable = is_proposable
    if last_backtest_at is not None:
        strategy.last_backtest_at = last_backtest_at
    if last_backtest_results is not None:
        strategy.last_backtest_results = last_backtest_results
    if train_metrics is not None:
        strategy.train_metrics = train_metrics
    if test_metrics is not None:
        strategy.test_metrics = test_metrics
    if evolution_attempts is not None:
        strategy.evolution_attempts = evolution_attempts
    if generalized is not None:
        strategy.generalized = generalized
    if per_symbol_performance is not None:
        strategy.per_symbol_performance = per_symbol_performance
    if explanation_human is not None:  # PHASE 1: Added
        strategy.explanation_human = explanation_human
    if risk_note is not None:  # PHASE 1: Added
        strategy.risk_note = risk_note
    
    db.commit()
    db.refresh(strategy)
    return strategy

def create_strategy_backtest(
    db: Session,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    total_return: float,
    win_rate: float,
    max_drawdown: float,
    avg_pnl: float,
    total_trades: int,
    results: Optional[Dict[str, Any]] = None
) -> StrategyBacktest:
    """Create a backtest record for a strategy."""
    backtest = StrategyBacktest(
        id=str(uuid.uuid4()),
        strategy_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        total_return=total_return,
        win_rate=win_rate,
        max_drawdown=max_drawdown,
        avg_pnl=avg_pnl,
        total_trades=total_trades,
        results=results or {},
    )
    db.add(backtest)
    db.commit()
    db.refresh(backtest)
    return backtest

def create_strategy_lineage(
    db: Session,
    parent_strategy_id: str,
    child_strategy_id: str,
    mutation_type: str,
    similarity_score: Optional[float] = None,
    creator_user_id: Optional[str] = None,
    royalty_percent_parent: Optional[float] = None,
    royalty_percent_child: Optional[float] = None,
    mutation_params: Optional[dict] = None
) -> StrategyLineage:
    """Create a lineage record linking parent and child strategies."""
    lineage = StrategyLineage(
        id=str(uuid.uuid4()),
        parent_strategy_id=parent_strategy_id,
        child_strategy_id=child_strategy_id,
        mutation_type=mutation_type,
        similarity_score=similarity_score,
        creator_user_id=creator_user_id,
        royalty_percent_parent=royalty_percent_parent,
        royalty_percent_child=royalty_percent_child,
        mutation_params=mutation_params,
    )
    db.add(lineage)
    db.commit()
    db.refresh(lineage)
    return lineage

def get_strategy_lineages_by_parent(
    db: Session,
    parent_strategy_id: str
) -> List[StrategyLineage]:
    """Get all lineage records where this strategy is the parent."""
    return db.query(StrategyLineage).filter(
        StrategyLineage.parent_strategy_id == parent_strategy_id
    ).all()

def get_strategy_lineages_by_child(
    db: Session,
    child_strategy_id: str
) -> List[StrategyLineage]:
    """Get all lineage records where this strategy is the child."""
    return db.query(StrategyLineage).filter(
        StrategyLineage.child_strategy_id == child_strategy_id
    ).all()

# ---------- User Trading Settings ----------
def get_user_trading_settings(db: Session, user_id: str) -> Optional[UserTradingSettings]:
    """Get user's trading settings."""
    return db.query(UserTradingSettings).filter(UserTradingSettings.user_id == user_id).first()

def create_user_trading_settings(
    db: Session,
    user_id: str,
    min_balance: float = 0.0,
    max_auto_trade_amount: float = 1000.0,
    max_risk_percent: float = 2.0,
    capital_range_min: float = 0.0,
    capital_range_max: float = 100000.0,
    auto_execution_enabled: bool = False,
    stop_under_balance: float = 0.0
) -> UserTradingSettings:
    """Create default trading settings for a user."""
    settings = UserTradingSettings(
        id=str(uuid.uuid4()),
        user_id=user_id,
        min_balance=min_balance,
        max_auto_trade_amount=max_auto_trade_amount,
        max_risk_percent=max_risk_percent,
        capital_range_min=capital_range_min,
        capital_range_max=capital_range_max,
        auto_execution_enabled=auto_execution_enabled,
        stop_under_balance=stop_under_balance,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings

def update_user_trading_settings(
    db: Session,
    user_id: str,
    min_balance: Optional[float] = None,
    max_auto_trade_amount: Optional[float] = None,
    max_risk_percent: Optional[float] = None,
    capital_range_min: Optional[float] = None,
    capital_range_max: Optional[float] = None,
    auto_execution_enabled: Optional[bool] = None,
    stop_under_balance: Optional[float] = None
) -> Optional[UserTradingSettings]:
    """Update user's trading settings."""
    settings = get_user_trading_settings(db, user_id)
    if not settings:
        return create_user_trading_settings(
            db, user_id,
            min_balance=min_balance or 0.0,
            max_auto_trade_amount=max_auto_trade_amount or 1000.0,
            max_risk_percent=max_risk_percent or 2.0,
            capital_range_min=capital_range_min or 0.0,
            capital_range_max=capital_range_max or 100000.0,
            auto_execution_enabled=auto_execution_enabled or False,
            stop_under_balance=stop_under_balance or 0.0
        )
    
    if min_balance is not None:
        settings.min_balance = min_balance
    if max_auto_trade_amount is not None:
        settings.max_auto_trade_amount = max_auto_trade_amount
    if max_risk_percent is not None:
        settings.max_risk_percent = max_risk_percent
    if capital_range_min is not None:
        settings.capital_range_min = capital_range_min
    if capital_range_max is not None:
        settings.capital_range_max = capital_range_max
    if auto_execution_enabled is not None:
        settings.auto_execution_enabled = auto_execution_enabled
    if stop_under_balance is not None:
        settings.stop_under_balance = stop_under_balance
    
    db.commit()
    db.refresh(settings)
    return settings

# ---------- Email OTP ----------
def create_email_otp(
    db: Session,
    email: str,
    otp_code: str,
    purpose: str,
    expires_in_minutes: int = 10
) -> EmailOTP:
    """Create a new email OTP record."""
    otp = EmailOTP(
        id=str(uuid.uuid4()),
        email=email.lower().strip(),
        otp_code=otp_code,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        used=False,
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def get_valid_otp(db: Session, email: str, otp_code: str, purpose: str) -> Optional[EmailOTP]:
    """Get a valid (unused, not expired) OTP for email verification or password reset."""
    otp = db.query(EmailOTP).filter(
        EmailOTP.email == email.lower().strip(),
        EmailOTP.otp_code == otp_code,
        EmailOTP.purpose == purpose,
        EmailOTP.used == False,
        EmailOTP.expires_at > datetime.now(timezone.utc)
    ).first()
    return otp


def mark_otp_as_used(db: Session, otp_id: str) -> None:
    """Mark an OTP as used."""
    otp = db.query(EmailOTP).filter(EmailOTP.id == otp_id).first()
    if otp:
        otp.used = True
        db.commit()


def cleanup_expired_otps(db: Session) -> int:
    """Delete expired OTPs. Returns count of deleted OTPs."""
    expired = db.query(EmailOTP).filter(
        EmailOTP.expires_at < datetime.now(timezone.utc)
    ).all()
    count = len(expired)
    for otp in expired:
        db.delete(otp)
    db.commit()
    return count

# ---------- Paper Account ----------
def get_or_create_paper_account(
    db: Session,
    user_id: str,
    starting_balance: float = 100000.0
) -> UserPaperAccount:
    """Get or create a paper account for a user."""
    paper_account = db.query(UserPaperAccount).filter(UserPaperAccount.user_id == user_id).first()
    if not paper_account:
        paper_account = UserPaperAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=starting_balance,
            starting_balance=starting_balance,
            last_reset_at=None,
        )
        db.add(paper_account)
        db.commit()
        db.refresh(paper_account)
    return paper_account


def get_paper_account(db: Session, user_id: str) -> Optional[UserPaperAccount]:
    """Get paper account for a user."""
    return db.query(UserPaperAccount).filter(UserPaperAccount.user_id == user_id).first()


def get_user_paper_account(db: Session, user_id: str) -> Optional[UserPaperAccount]:
    """Get paper account for a user (alias for get_paper_account)."""
    return get_paper_account(db, user_id)


def update_paper_account_balance(
    db: Session,
    user_id: str,
    new_balance: float
) -> UserPaperAccount:
    """Update paper account balance."""
    paper_account = get_or_create_paper_account(db, user_id)
    paper_account.balance = new_balance
    db.commit()
    db.refresh(paper_account)
    return paper_account


def update_user_paper_account(
    db: Session,
    user_id: str,
    balance: Optional[float] = None,
    starting_balance: Optional[float] = None
) -> UserPaperAccount:
    """Update paper account (alias for update_paper_account_balance)."""
    paper_account = get_or_create_paper_account(db, user_id)
    if balance is not None:
        paper_account.balance = balance
    if starting_balance is not None:
        paper_account.starting_balance = starting_balance
    db.commit()
    db.refresh(paper_account)
    return paper_account


def reset_paper_account(
    db: Session,
    user_id: str,
    starting_balance: Optional[float] = None
) -> UserPaperAccount:
    """Reset paper account to starting balance."""
    paper_account = get_or_create_paper_account(db, user_id)
    
    # Use provided starting_balance or keep existing
    if starting_balance is not None:
        paper_account.starting_balance = starting_balance
    
    paper_account.balance = paper_account.starting_balance
    paper_account.last_reset_at = datetime.now(timezone.utc)
    
    # Close all open PAPER trades for this user
    open_trades = db.query(Trade).filter(
        Trade.user_id == user_id,
        Trade.mode == TradeMode.PAPER,
        Trade.status == TradeStatus.OPEN
    ).all()
    
    # Mark trades as closed (or delete them - depends on requirements)
    # For now, we'll just update the balance and leave trades as historical record
    # In production, you might want to close them properly
    
    db.commit()
    db.refresh(paper_account)
    return paper_account


# ---------- Feedback ----------
def create_feedback(
    db: Session,
    user_id: Optional[str],
    page_or_context: str,
    category: str,
    message: str,
) -> Feedback:
    """Create a feedback entry."""
    feedback = Feedback(
        id=str(uuid.uuid4()),
        user_id=user_id,
        page_or_context=page_or_context,
        category=category,
        message=message,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback(
    db: Session,
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> List[Feedback]:
    """List feedback entries (admin function)."""
    query = db.query(Feedback)
    if user_id:
        query = query.filter(Feedback.user_id == user_id)
    if category:
        query = query.filter(Feedback.category == category)
    return query.order_by(Feedback.created_at.desc()).limit(limit).all()

# ---------- Admin Notifications ----------
def create_admin_notification(
    db: Session,
    title: str,
    message: str,
    notification_type: str = "info",
    expires_at: Optional[datetime] = None
) -> AdminNotification:
    """Create a new admin notification."""
    notification = AdminNotification(
        id=str(uuid.uuid4()),
        title=title,
        message=message,
        notification_type=notification_type,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def get_active_notifications(db: Session, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all active notifications that haven't been read by the user (if user_id provided)."""
    now = datetime.now(timezone.utc)
    query = db.query(AdminNotification).filter(
        AdminNotification.is_active == True,
        or_(
            AdminNotification.expires_at.is_(None),
            AdminNotification.expires_at > now
        )
    ).order_by(AdminNotification.created_at.desc())
    
    notifications = query.all()
    result = []
    
    for notif in notifications:
        read = False
        if user_id:
            read_record = db.query(UserNotificationRead).filter(
                UserNotificationRead.user_id == user_id,
                UserNotificationRead.notification_id == notif.id
            ).first()
            read = read_record is not None
        
        if not read:
            result.append({
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "created_at": notif.created_at.isoformat(),
                "expires_at": notif.expires_at.isoformat() if notif.expires_at else None,
            })
    
    return result

def mark_notification_as_read(db: Session, user_id: str, notification_id: str) -> bool:
    """Mark a notification as read by a user."""
    # Check if already read
    existing = db.query(UserNotificationRead).filter(
        UserNotificationRead.user_id == user_id,
        UserNotificationRead.notification_id == notification_id
    ).first()
    
    if existing:
        return True
    
    read_record = UserNotificationRead(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notification_id=notification_id,
    )
    db.add(read_record)
    db.commit()
    return True
