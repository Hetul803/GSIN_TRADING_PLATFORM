# backend/db/models.py
from __future__ import annotations
from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Text, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from enum import Enum
from .session import Base

# Enums
class UserRole(str, Enum):
    USER = "user"
    PRO = "pro"
    CREATOR = "creator"
    ADMIN = "admin"

class SubscriptionTier(str, Enum):
    USER = "user"
    PRO = "pro"
    CREATOR = "creator"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIAL = "trial"

class GroupRole(str, Enum):
    OWNER = "owner"
    MODERATOR = "moderator"
    MEMBER = "member"

class TradeMode(str, Enum):
    PAPER = "PAPER"
    REAL = "REAL"

class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class AssetType(str, Enum):
    STOCK = "STOCK"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    OTHER = "OTHER"

class TradeSource(str, Enum):
    MANUAL = "MANUAL"
    BRAIN = "BRAIN"

# Legacy models (from original codebase)
class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(32))
    stype: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON)
    fees: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    period: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(32))
    stype: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON)
    ret: Mapped[float] = mapped_column(Float)
    sharpe: Mapped[float] = mapped_column(Float)
    dd: Mapped[float] = mapped_column(Float)
    trades: Mapped[int] = mapped_column(Integer)
    turnover: Mapped[float] = mapped_column(Float)
    regime: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Royalty(Base):
    __tablename__ = "royalties"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    epoch: Mapped[str] = mapped_column(String(64))
    points: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Memory(Base):
    __tablename__ = "memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    v0: Mapped[float] = mapped_column(Float)  # return
    v1: Mapped[float] = mapped_column(Float)  # sharpe
    v2: Mapped[float] = mapped_column(Float)  # -dd
    v3: Mapped[float] = mapped_column(Float)  # trades
    v4: Mapped[float] = mapped_column(Float)  # turnover
    v5: Mapped[float] = mapped_column(Float)  # regime_trend
    v6: Mapped[float] = mapped_column(Float)  # regime_vol
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    meta: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# New models for user management
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Hashed password, nullable for OAuth users
    # OAuth fields
    auth_provider: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # "google", "github", "twitter", "email"
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # OAuth provider's user ID
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether email is verified
    # User role and subscription
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.USER)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(SQLEnum(SubscriptionTier), default=SubscriptionTier.USER)  # Legacy field, kept for compatibility
    # Current subscription plan (FK to subscription_plans)
    current_plan_id: Mapped[str | None] = mapped_column(String, ForeignKey("subscription_plans.id"), nullable=True, index=True)
    # Resolved royalty percentage (from plan or overridden)
    royalty_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # If None, use plan's default_royalty_percent
    # PHASE 5: Tutorial flag
    has_seen_tutorial: Mapped[bool] = mapped_column(Boolean, default=False)  # Has user completed onboarding tutorial
    # PHASE 6: Broker connection status
    broker_connected: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether user has connected a broker
    broker_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "alpaca", "manual", etc.
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    current_plan: Mapped["SubscriptionPlan | None"] = relationship("SubscriptionPlan", foreign_keys=[current_plan_id], post_update=True)
    subscriptions: Mapped[list["UserSubscription"]] = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    owned_groups: Mapped[list["Group"]] = relationship("Group", back_populates="owner", cascade="all, delete-orphan")
    group_memberships: Mapped[list["GroupMember"]] = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    group_messages: Mapped[list["GroupMessage"]] = relationship("GroupMessage", back_populates="user", cascade="all, delete-orphan")
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    strategies: Mapped[list["UserStrategy"]] = relationship("UserStrategy", back_populates="user", cascade="all, delete-orphan")
    trading_settings: Mapped["UserTradingSettings | None"] = relationship("UserTradingSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    paper_account: Mapped["UserPaperAccount | None"] = relationship("UserPaperAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    feedback: Mapped[list["Feedback"]] = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    notification_reads: Mapped[list["UserNotificationRead"]] = relationship("UserNotificationRead", back_populates="user", cascade="all, delete-orphan")
    royalties_received: Mapped[list["RoyaltyLedger"]] = relationship("RoyaltyLedger", foreign_keys="RoyaltyLedger.user_id")  # PHASE 5
    referrals_sent: Mapped[list["Referral"]] = relationship("Referral", foreign_keys="Referral.referrer_id")  # PHASE 5
    referrals_received: Mapped[list["Referral"]] = relationship("Referral", foreign_keys="Referral.referred_id")  # PHASE 5
    broker_connection: Mapped["BrokerConnection | None"] = relationship("BrokerConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")  # PHASE 6


class EmailOTP(Base):
    """Email OTP codes for verification and password reset."""
    __tablename__ = "email_otps"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    email: Mapped[str] = mapped_column(String(255), index=True)
    otp_code: Mapped[str] = mapped_column(String(6))  # 6-digit code
    purpose: Mapped[str] = mapped_column(String(32))  # "verification" or "password_reset"
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    plan_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # e.g. "USER", "USER_PLUS_UPLOAD", "CREATOR"
    name: Mapped[str] = mapped_column(String(128))  # Display name, e.g. "User", "User + Upload", "Creator"
    price_monthly: Mapped[int] = mapped_column(Integer)  # in cents (e.g. 3999 = $39.99)
    default_royalty_percent: Mapped[float] = mapped_column(Float)  # Default royalty % for this plan (Starter/Pro: 0%, Creator: 5%)
    platform_fee_percent: Mapped[float] = mapped_column(Float)  # GSIN platform fee % (Starter: 7%, Pro: 5%, Creator: 3%)
    performance_fee_percent: Mapped[float] = mapped_column(Float)  # Legacy field, kept for compatibility
    is_creator_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    subscriptions: Mapped[list["UserSubscription"]] = relationship("UserSubscription", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(String, ForeignKey("subscription_plans.id"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    current_period_start: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")

class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Optional description
    max_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_discoverable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    price_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in cents
    join_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # Short, human-friendly code (6-10 chars, alphanumeric)
    invite_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)  # Legacy field, kept for compatibility
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_groups")
    members: Mapped[list["GroupMember"]] = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages: Mapped[list["GroupMessage"]] = relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan")
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="group")

class GroupMember(Base):
    __tablename__ = "group_members"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    group_id: Mapped[str] = mapped_column(String, ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[GroupRole] = mapped_column(SQLEnum(GroupRole), default=GroupRole.MEMBER)
    joined_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # Alias for joined_at
    
    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="group_memberships")

class GroupMessage(Base):
    __tablename__ = "group_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    group_id: Mapped[str] = mapped_column(String, ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    encrypted_content: Mapped[str] = mapped_column(Text)  # Encrypted message content
    message_type: Mapped[str | None] = mapped_column(String(32), nullable=True, default="TEXT")  # "TEXT", "TRADE_PROPOSAL", or "STRATEGY"
    strategy_id: Mapped[str | None] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="SET NULL"), nullable=True, index=True)  # For strategy messages
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="messages")
    user: Mapped["User"] = relationship("User", back_populates="group_messages")
    strategy: Mapped["UserStrategy | None"] = relationship("UserStrategy")  # Strategy attached to message
    
    # For compatibility with crud functions that use 'content'
    @property
    def content(self) -> str:
        """Alias for encrypted_content (for backward compatibility)."""
        return self.encrypted_content

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), default=AssetType.STOCK)
    side: Mapped[TradeSide] = mapped_column(SQLEnum(TradeSide))
    quantity: Mapped[float] = mapped_column(Float)  # Changed from Integer to support fractional shares/crypto
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # Nullable until closed
    status: Mapped[TradeStatus] = mapped_column(SQLEnum(TradeStatus), default=TradeStatus.OPEN, index=True)  # Indexed for frequent filtering
    mode: Mapped[TradeMode] = mapped_column(SQLEnum(TradeMode), default=TradeMode.PAPER, index=True)  # Indexed for frequent filtering
    source: Mapped[TradeSource] = mapped_column(SQLEnum(TradeSource), default=TradeSource.MANUAL)  # MANUAL or BRAIN
    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)  # Indexed for ordering
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Nullable until closed
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)  # Computed P&L when closed
    strategy_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)  # For later royalties feature
    group_id: Mapped[str | None] = mapped_column(String, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True)  # For later group-based trading
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Legacy fields (kept for compatibility)
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)  # Alias for realized_pnl
    strategy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Denormalized for easier queries
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trades")
    group: Mapped["Group | None"] = relationship("Group", back_populates="trades")

class UserStrategy(Base):
    """
    User Strategy Model - Designed for Genetic Algorithm Evolution.
    
    This model supports the evolution worker's genetic algorithm by tracking:
    - Status progression: experiment → candidate → proposable → discarded
    - Backtest metrics: results, train/test metrics for overfitting detection
    - Evolution tracking: attempts, score, promotion flags
    - Lineage: Parent-child relationships via StrategyLineage table (not direct parent_id)
    
    Note: 'generation' is calculated dynamically from StrategyLineage, not stored.
    """
    __tablename__ = "user_strategies"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON)  # Strategy parameters (JSON)
    ruleset: Mapped[dict] = mapped_column(JSON)  # Strategy ruleset/logic (JSON)
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), default=AssetType.STOCK)
    
    # GENETIC ALGORITHM FIELDS (Required by evolution_worker.py)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Unified strategy score (0-1) - Used for ranking
    status: Mapped[str] = mapped_column(String(32), default="experiment", index=True)  # experiment, candidate, proposable, discarded - CRITICAL for promotion tracking
    last_backtest_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)  # Used for prioritization in evolution cycles
    last_backtest_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Latest backtest results - CRITICAL for status determination
    train_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Train set metrics (for overfitting detection)
    test_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Test set metrics (for overfitting detection)
    evolution_attempts: Mapped[int] = mapped_column(Integer, default=0)  # Number of mutation/evolution attempts - CRITICAL for discard logic
    is_proposable: Mapped[bool] = mapped_column(Boolean, default=False)  # True if status="proposable" and meets all thresholds - CRITICAL promotion flag
    
    # ADDITIONAL FIELDS
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    generalized: Mapped[bool] = mapped_column(Boolean, default=False)  # True if strategy performs well on >2 assets
    per_symbol_performance: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Performance metrics per symbol (for generalized strategies)
    explanation_human: Mapped[str | None] = mapped_column(Text, nullable=True)  # PHASE 1: Human-readable explanation of strategy
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # PHASE 1: Risk warning/note for users
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    # Note: Parent relationships are tracked via StrategyLineage table, not a direct parent_id column
    # This allows for multiple parents (crossover mutations) and complex lineage trees
    user: Mapped["User"] = relationship("User", back_populates="strategies")
    backtests: Mapped[list["StrategyBacktest"]] = relationship("StrategyBacktest", back_populates="strategy", cascade="all, delete-orphan")
    parent_lineages: Mapped[list["StrategyLineage"]] = relationship("StrategyLineage", foreign_keys="StrategyLineage.parent_strategy_id", back_populates="parent_strategy")
    child_lineages: Mapped[list["StrategyLineage"]] = relationship("StrategyLineage", foreign_keys="StrategyLineage.child_strategy_id", back_populates="child_strategy")

class StrategyBacktest(Base):
    __tablename__ = "strategy_backtests"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    strategy_id: Mapped[str] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16))  # e.g. "1d", "1h"
    start_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    total_return: Mapped[float] = mapped_column(Float)  # Total return percentage
    win_rate: Mapped[float] = mapped_column(Float)  # Win rate (0-1)
    max_drawdown: Mapped[float] = mapped_column(Float)  # Maximum drawdown
    avg_pnl: Mapped[float] = mapped_column(Float)  # Average P&L per trade
    total_trades: Mapped[int] = mapped_column(Integer)  # Total number of trades
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # Sharpe ratio
    results: Mapped[dict] = mapped_column(JSON)  # Full backtest results (equity curve, etc.)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    strategy: Mapped["UserStrategy"] = relationship("UserStrategy", back_populates="backtests")

class RoyaltyLedger(Base):
    """
    PHASE 5: Royalty ledger for tracking strategy creator royalties.
    Records royalties paid to strategy owners when their strategies are used profitably.
    """
    __tablename__ = "royalty_ledger"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)  # Strategy owner
    strategy_id: Mapped[str | None] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="SET NULL"), nullable=True, index=True)  # Strategy that generated profit
    trade_id: Mapped[str] = mapped_column(String, ForeignKey("trades.id", ondelete="CASCADE"), index=True)  # Trade that generated profit
    royalty_amount: Mapped[float] = mapped_column(Float)  # Royalty amount (profit * royalty_rate)
    royalty_rate: Mapped[float] = mapped_column(Float)  # Royalty rate used (e.g., 0.03 for 3%)
    platform_fee: Mapped[float] = mapped_column(Float)  # Platform fee (GSIN's cut)
    platform_fee_rate: Mapped[float] = mapped_column(Float)  # Platform fee rate (e.g., 0.05 for 5%)
    net_amount: Mapped[float] = mapped_column(Float)  # Net amount to strategy owner (royalty_amount - platform_fee)
    trade_profit: Mapped[float] = mapped_column(Float)  # Original trade profit (for reference)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], overlaps="royalties_received")
    strategy: Mapped["UserStrategy | None"] = relationship("UserStrategy")
    trade: Mapped["Trade"] = relationship("Trade")

class Referral(Base):
    """
    PHASE 5: Referral tracking for group invites and user referrals.
    """
    __tablename__ = "referrals"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    referrer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)  # User who referred
    referred_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # User who was referred (null if pending)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # Unique referral code
    referral_type: Mapped[str] = mapped_column(String(32), index=True)  # "group_invite", "user_signup", etc.
    group_id: Mapped[str | None] = mapped_column(String, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)  # If group invite
    used: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether referral was used
    used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id], overlaps="referrals_sent")
    referred: Mapped["User | None"] = relationship("User", foreign_keys=[referred_id], overlaps="referrals_received")
    group: Mapped["Group | None"] = relationship("Group")

class StrategyLineage(Base):
    __tablename__ = "strategy_lineage"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    parent_strategy_id: Mapped[str] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="CASCADE"), index=True)
    child_strategy_id: Mapped[str] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="CASCADE"), index=True)
    mutation_type: Mapped[str] = mapped_column(String(64))  # Type of mutation (e.g. "parameter_tweak", "timeframe_change")
    mutation_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Mutation parameters
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Similarity score between parent and child
    creator_user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # User who created the mutation
    royalty_percent_parent: Mapped[float | None] = mapped_column(Float, nullable=True)  # Royalty % for parent strategy creator
    royalty_percent_child: Mapped[float | None] = mapped_column(Float, nullable=True)  # Royalty % for child strategy creator
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    parent_strategy: Mapped["UserStrategy"] = relationship("UserStrategy", foreign_keys=[parent_strategy_id], back_populates="parent_lineages")
    child_strategy: Mapped["UserStrategy"] = relationship("UserStrategy", foreign_keys=[child_strategy_id], back_populates="child_lineages")
    creator: Mapped["User | None"] = relationship("User")

class UserTradingSettings(Base):
    __tablename__ = "user_trading_settings"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    min_balance: Mapped[float] = mapped_column(Float, default=0.0)  # Minimum balance before stopping trades
    max_auto_trade_amount: Mapped[float] = mapped_column(Float, default=1000.0)  # Maximum amount per auto trade
    max_risk_percent: Mapped[float] = mapped_column(Float, default=2.0)  # Maximum risk per trade (% of capital)
    capital_range_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # Minimum capital for auto trading
    capital_range_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # Maximum capital for auto trading
    auto_execution_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # Enable auto execution
    stop_under_balance: Mapped[float | None] = mapped_column(Float, nullable=True)  # Stop trading if balance falls below this
    daily_profit_target: Mapped[float | None] = mapped_column(Float, nullable=True)  # Daily profit goal (e.g., 100.0 for $100/day)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trading_settings")

class UserPaperAccount(Base):
    """Paper trading account balance tracking."""
    __tablename__ = "user_paper_accounts"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    balance: Mapped[float] = mapped_column(Float, default=100000.0)  # Current paper balance
    starting_balance: Mapped[float] = mapped_column(Float, default=100000.0)  # Starting balance (for reset)
    last_reset_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Last reset timestamp
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="paper_account")

class Feedback(Base):
    """User feedback and suggestions."""
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Nullable for anonymous feedback
    page_or_context: Mapped[str] = mapped_column(String(256))  # e.g., "/terminal", "/brain"
    category: Mapped[str] = mapped_column(String(32))  # "bug", "feature", "idea", "other"
    message: Mapped[str] = mapped_column(Text)  # Feedback message
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="feedback")


# PHASE 2: Admin Settings Model (if not exists)
# Note: AdminNotification may already exist, so we'll check before adding

class AdminNotification(Base):
    """Admin notifications/announcements visible to all users."""
    __tablename__ = "admin_notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    title: Mapped[str] = mapped_column(String(255))  # Notification title
    message: Mapped[str] = mapped_column(Text)  # Notification message
    notification_type: Mapped[str] = mapped_column(String(32), default="info")  # "info", "warning", "success", "update"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Whether notification is active
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # Optional expiration


class UserNotificationRead(Base):
    """Tracks which users have read/dismissed which notifications."""
    __tablename__ = "user_notification_reads"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    notification_id: Mapped[str] = mapped_column(String, ForeignKey("admin_notifications.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notification_reads")
    notification: Mapped["AdminNotification"] = relationship("AdminNotification")


# PHASE 2: Admin Settings Model
class AdminSettings(Base):
    __tablename__ = "admin_settings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")  # Single row
    platform_fee_percent: Mapped[float] = mapped_column(Float, default=5.0)  # Default 5%
    creator_fee_percent: Mapped[float] = mapped_column(Float, default=3.0)  # Default 3%
    pnl_fee_threshold_usd: Mapped[float] = mapped_column(Float, default=1000.0)  # Default $1000
    grace_months_for_good_users: Mapped[int] = mapped_column(Integer, default=2)  # Default 2 months
    basic_price: Mapped[float] = mapped_column(Float, default=39.99)
    pro_price: Mapped[float] = mapped_column(Float, default=49.99)
    creator_price: Mapped[float] = mapped_column(Float, default=99.99)
    max_concurrent_backtests: Mapped[int] = mapped_column(Integer, default=3)  # Max simultaneous backtests
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String, nullable=True)  # Admin user ID who last updated

# PHASE 2: Promo Code Model
class PromoCode(Base):
    __tablename__ = "promo_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # Promo code string
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # Percentage discount
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # Fixed amount discount
    applicable_tiers: Mapped[list[str]] = mapped_column(JSON, default=list)  # List of tiers (e.g., ["basic", "pro"])
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Max number of uses (None = unlimited)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)  # Current number of uses
    expiry_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)  # Admin user ID

# PHASE 2: Notification Model
class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # None = all users
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    read_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)  # Admin user ID who created

class StrategyRoyalty(Base):
    """Tracks royalties paid to strategy creators when their strategies generate profit."""
    __tablename__ = "strategy_royalties"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    trade_id: Mapped[str] = mapped_column(String, ForeignKey("trades.id", ondelete="CASCADE"), index=True)
    strategy_id: Mapped[str] = mapped_column(String, ForeignKey("user_strategies.id", ondelete="CASCADE"), index=True)
    strategy_creator_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)  # User who uploaded the strategy
    trade_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)  # User who executed the trade
    profit_amount: Mapped[float] = mapped_column(Float)  # Profit from the trade (realized_pnl)
    royalty_percent: Mapped[float] = mapped_column(Float)  # Royalty percentage (5% for strategy creators)
    royalty_amount: Mapped[float] = mapped_column(Float)  # Calculated royalty: profit_amount * royalty_percent / 100
    performance_fee_percent: Mapped[float] = mapped_column(Float)  # Platform performance fee (3-7% based on user's plan)
    performance_fee_amount: Mapped[float] = mapped_column(Float)  # Calculated performance fee: profit_amount * performance_fee_percent / 100
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    trade: Mapped["Trade"] = relationship("Trade")
    strategy: Mapped["UserStrategy"] = relationship("UserStrategy")
    strategy_creator: Mapped["User"] = relationship("User", foreign_keys=[strategy_creator_id])
    trade_user: Mapped["User"] = relationship("User", foreign_keys=[trade_user_id])


class UserAgreement(Base):
    """
    Tracks user agreements (Terms of Service, Privacy Policy, Risk Disclosure).
    Required before users can trade.
    """
    __tablename__ = "user_agreements"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agreement_type: Mapped[str] = mapped_column(String(64))  # "terms", "privacy", "risk_disclosure"
    agreement_version: Mapped[str] = mapped_column(String(32))  # Version of agreement (e.g., "1.0")
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)  # IP address when accepted
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)  # User agent when accepted
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User")


class BrokerConnection(Base):
    """
    PHASE 6: Encrypted broker connection credentials per user.
    Stores encrypted API keys for Alpaca or other brokers.
    """
    __tablename__ = "broker_connections"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # UUID as string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)  # One connection per user
    provider: Mapped[str] = mapped_column(String(32), index=True)  # "alpaca", "manual", etc.
    connection_type: Mapped[str] = mapped_column(String(32))  # "oauth" or "api_key"
    
    # Encrypted credentials (Fernet-encrypted)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted API key
    encrypted_api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted API secret
    encrypted_oauth_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted OAuth token (for Alpaca OAuth)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Encrypted refresh token
    
    # Connection metadata
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether connection has been verified
    verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Alpaca-specific fields
    alpaca_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Alpaca account ID
    alpaca_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)  # paper-api or api
    
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="broker_connection")
