# backend/api/admin_metrics.py
"""
PHASE 2: Admin Metrics Dashboard API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db.models import User, UserStrategy, Trade, SubscriptionPlan, UserSubscription, RoyaltyLedger, UserRole, TradeStatus, SubscriptionTier, SubscriptionStatus, TradeSource, StrategyBacktest
from ..strategy_engine.status_manager import StrategyStatus
from ..db import crud
from ..market_data.market_data_provider import get_provider

router = APIRouter(prefix="/admin/metrics", tags=["admin"])


def verify_admin(db: Session, user_id: str) -> None:
    """Verify that the user is an admin."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


class MetricsSummaryResponse(BaseModel):
    users: Dict[str, Any]
    strategies: Dict[str, Any]
    trading: Dict[str, Any]
    revenue: Dict[str, Any]
    top_strategies: Dict[str, Any]
    system: Dict[str, Any]


@router.get("/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get comprehensive metrics summary for admin dashboard."""
    verify_admin(db, user_id)
    
    try:
        # FIX: Disable cache for real-time updates (or use shorter TTL)
        # Cache expensive metrics query (5 second TTL for near real-time updates)
        from ..utils.response_cache import get_cache
        cache = get_cache()
        
        cached_result = cache.get("admin_metrics_summary", user_id, ttl_seconds=5)
        if cached_result is not None:
            return cached_result
        
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # ========== USER METRICS ==========
        total_users = db.query(User).count()
        
        # Active users (updated profile within last 24h - proxy for activity)
        # Note: User model doesn't have last_login_at, using updated_at as proxy
        active_users = db.query(User).filter(
            User.updated_at >= last_24h
        ).count()
        
        # Current month's paying users by tier
        current_month_subs = db.query(UserSubscription).filter(
            UserSubscription.status == SubscriptionStatus.ACTIVE,
            UserSubscription.current_period_start >= current_month_start
        ).all()
        
        subs_by_tier_current_month = {"basic": 0, "pro": 0, "creator": 0}
        for sub in current_month_subs:
            if sub.plan:
                plan_code_lower = sub.plan.plan_code.lower()
                if "basic" in plan_code_lower or "user" in plan_code_lower:
                    subs_by_tier_current_month["basic"] += 1
                elif "pro" in plan_code_lower:
                    subs_by_tier_current_month["pro"] += 1
                elif "creator" in plan_code_lower:
                    subs_by_tier_current_month["creator"] += 1
        
        # ========== STRATEGY METRICS ==========
        # Total active strategies
        total_active_strategies = db.query(UserStrategy).filter(UserStrategy.is_active == True).count()
        
        # Strategies pending backtest (never backtested OR status is PENDING_REVIEW/EXPERIMENT)
        # FIX: Use SQLAlchemy's or_() instead of Python's | operator
        try:
            strategies_pending_backtest = db.query(UserStrategy).filter(
                UserStrategy.is_active == True
            ).filter(
                or_(
                    UserStrategy.last_backtest_at.is_(None),
                    UserStrategy.status == StrategyStatus.PENDING_REVIEW,
                    UserStrategy.status == StrategyStatus.EXPERIMENT
                )
            ).count()
        except Exception as e:
            # Fallback to simple query
            strategies_pending_backtest = db.query(UserStrategy).filter(
                UserStrategy.last_backtest_at.is_(None),
                UserStrategy.is_active == True
            ).count()
        
        # Strategies currently backtesting (backtested in last hour - simplified)
        one_hour_ago = now - timedelta(hours=1)
        try:
            strategies_currently_backtesting = db.query(UserStrategy).filter(
                UserStrategy.last_backtest_at >= one_hour_ago,
                UserStrategy.status.in_([StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE])
            ).count()
        except Exception:
            strategies_currently_backtesting = 0
        
        # Brain-generated strategies (evolution_attempts > 0)
        try:
            brain_strategies = db.query(UserStrategy).filter(UserStrategy.evolution_attempts > 0)
            brain_total = brain_strategies.count()
            brain_active = brain_strategies.filter(UserStrategy.is_active == True).count()
            brain_pending_backtest = brain_strategies.filter(UserStrategy.last_backtest_at.is_(None)).count()
            brain_currently_backtesting = brain_strategies.filter(
                UserStrategy.last_backtest_at >= one_hour_ago,
                UserStrategy.status.in_([StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE])
            ).count()
        except Exception:
            brain_total = brain_active = brain_pending_backtest = brain_currently_backtesting = 0
        
        # User-generated strategies (evolution_attempts == 0)
        try:
            user_strategies = db.query(UserStrategy).filter(UserStrategy.evolution_attempts == 0)
            user_total = user_strategies.count()
            user_active = user_strategies.filter(UserStrategy.is_active == True).count()
            user_pending_backtest = user_strategies.filter(UserStrategy.last_backtest_at.is_(None)).count()
            user_currently_backtesting = user_strategies.filter(
                UserStrategy.last_backtest_at >= one_hour_ago,
                UserStrategy.status.in_([StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE])
            ).count()
        except Exception:
            user_total = user_active = user_pending_backtest = user_currently_backtesting = 0
        
        # ========== TRADING METRICS ==========
        # Brain-generated strategy trades (source = BRAIN)
        brain_trades = db.query(Trade).filter(
            Trade.source == TradeSource.BRAIN,
            Trade.status == TradeStatus.CLOSED
        )
        brain_trades_count = brain_trades.count()
        brain_pnl = float(brain_trades.with_entities(func.sum(Trade.realized_pnl)).scalar() or 0.0)
        
        # Calculate Sharpe and Drawdown for brain trades
        brain_sharpe = 0.0
        brain_drawdown = 0.0
        if brain_trades_count > 0:
            # Get all brain trade PnLs
            brain_pnls = [t.realized_pnl for t in brain_trades.all() if t.realized_pnl is not None]
            if brain_pnls:
                import statistics
                if len(brain_pnls) > 1:
                    mean_pnl = statistics.mean(brain_pnls)
                    std_pnl = statistics.stdev(brain_pnls)
                    brain_sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0.0
                
                # Calculate max drawdown (simplified - max consecutive negative PnL)
                cumulative = 0
                max_dd = 0
                peak = 0
                for pnl in brain_pnls:
                    cumulative += pnl
                    if cumulative > peak:
                        peak = cumulative
                    drawdown = peak - cumulative
                    if drawdown > max_dd:
                        max_dd = drawdown
                brain_drawdown = max_dd
        
        # User-generated strategy trades (source = MANUAL with strategy_id)
        user_trades = db.query(Trade).filter(
            Trade.source == TradeSource.MANUAL,
            Trade.strategy_id.isnot(None),
            Trade.status == TradeStatus.CLOSED
        )
        user_trades_count = user_trades.count()
        user_pnl = float(user_trades.with_entities(func.sum(Trade.realized_pnl)).scalar() or 0.0)
        
        # Calculate Sharpe and Drawdown for user trades
        user_sharpe = 0.0
        user_drawdown = 0.0
        if user_trades_count > 0:
            user_pnls = [t.realized_pnl for t in user_trades.all() if t.realized_pnl is not None]
            if user_pnls:
                import statistics
                if len(user_pnls) > 1:
                    mean_pnl = statistics.mean(user_pnls)
                    std_pnl = statistics.stdev(user_pnls)
                    user_sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0.0
                
                cumulative = 0
                max_dd = 0
                peak = 0
                for pnl in user_pnls:
                    cumulative += pnl
                    if cumulative > peak:
                        peak = cumulative
                    drawdown = peak - cumulative
                    if drawdown > max_dd:
                        max_dd = drawdown
                user_drawdown = max_dd
        
        # ========== TOP STRATEGIES ==========
        # Top 5 most used strategies (by trade count)
        top_used = db.query(
            UserStrategy.id,
            UserStrategy.name,
            func.count(Trade.id).label("trade_count")
        ).join(
            Trade, UserStrategy.id == Trade.strategy_id, isouter=True
        ).group_by(
            UserStrategy.id, UserStrategy.name
        ).order_by(desc("trade_count")).limit(5).all()
        
        top_used_list = [
            {
                "strategy_id": s.id,
                "strategy_name": s.name,
                "trade_count": s.trade_count or 0
            }
            for s in top_used
        ]
        
        # Top 5 strategies by Sharpe ratio (from backtests)
        top_sharpe = db.query(
            UserStrategy.id,
            UserStrategy.name,
            func.avg(StrategyBacktest.sharpe_ratio).label("avg_sharpe")
        ).join(
            StrategyBacktest, UserStrategy.id == StrategyBacktest.strategy_id, isouter=True
        ).filter(
            StrategyBacktest.sharpe_ratio.isnot(None)
        ).group_by(
            UserStrategy.id, UserStrategy.name
        ).order_by(desc("avg_sharpe")).limit(5).all()
        
        top_sharpe_list = [
            {
                "strategy_id": s.id,
                "strategy_name": s.name,
                "sharpe_ratio": float(s.avg_sharpe) if s.avg_sharpe else 0.0
            }
            for s in top_sharpe
        ]
        
        # Top 5 strategies by profit (from trades)
        top_profit = db.query(
            UserStrategy.id,
            UserStrategy.name,
            func.sum(Trade.realized_pnl).label("total_profit")
        ).join(
            Trade, UserStrategy.id == Trade.strategy_id, isouter=True
        ).filter(
            Trade.status == TradeStatus.CLOSED,
            Trade.realized_pnl.isnot(None)
        ).group_by(
            UserStrategy.id, UserStrategy.name
        ).order_by(desc("total_profit")).limit(5).all()
        
        top_profit_list = [
            {
                "strategy_id": s.id,
                "strategy_name": s.name,
                "total_profit": float(s.total_profit) if s.total_profit else 0.0
            }
            for s in top_profit
        ]
        
        # Top 5 strategies by drawdown (from backtests - lower is better, so we order ascending)
        top_drawdown = db.query(
            UserStrategy.id,
            UserStrategy.name,
            func.avg(StrategyBacktest.max_drawdown).label("avg_drawdown")
        ).join(
            StrategyBacktest, UserStrategy.id == StrategyBacktest.strategy_id, isouter=True
        ).filter(
            StrategyBacktest.max_drawdown.isnot(None)
        ).group_by(
            UserStrategy.id, UserStrategy.name
        ).order_by("avg_drawdown").limit(5).all()  # Ascending - lower drawdown is better
        
        top_drawdown_list = [
            {
                "strategy_id": s.id,
                "strategy_name": s.name,
                "drawdown": float(abs(s.avg_drawdown)) if s.avg_drawdown else 0.0
            }
            for s in top_drawdown
        ]
        
        # ========== REVENUE METRICS ==========
        # Total revenue from subscriptions (MRR)
        total_subscription_mrr = 0.0
        try:
            user_subs = db.query(UserSubscription).filter(UserSubscription.status == SubscriptionStatus.ACTIVE).all()
            for sub in user_subs:
                if sub.plan and sub.plan.price_monthly:
                    total_subscription_mrr += sub.plan.price_monthly / 100.0  # Convert cents to dollars
        except:
            pass
        
        # Total royalties (paid)
        total_royalties = float(db.query(func.sum(RoyaltyLedger.royalty_amount)).filter(
            RoyaltyLedger.paid == True
        ).scalar() or 0.0)
        
        # Total platform fees (paid)
        total_platform_fees = float(db.query(func.sum(RoyaltyLedger.platform_fee)).filter(
            RoyaltyLedger.paid == True
        ).scalar() or 0.0)
        
        # ========== SYSTEM METRICS ==========
        market_data_provider_status = "ok"
        try:
            provider = get_provider()
            if provider:
                test_price = provider.get_price("AAPL")
                market_data_provider_status = "ok" if test_price else "degraded"
            else:
                market_data_provider_status = "degraded"
        except:
            market_data_provider_status = "down"
        
        evolution_worker_status = "unknown"
        
        db_status = "ok"
        try:
            db.execute("SELECT 1")
        except:
            db_status = "down"
        
        redis_status = "not_configured"
        error_count_last_24h = 0
        
        result = MetricsSummaryResponse(
            users={
                "total_users": total_users,
                "active_users": active_users,
                "current_month_paying_by_tier": subs_by_tier_current_month,
            },
            strategies={
                "total_active": total_active_strategies,
                "pending_backtest": strategies_pending_backtest,
                "currently_backtesting": strategies_currently_backtesting,
                "user_generated": {
                    "total": user_total,
                    "active": user_active,
                    "pending_backtest": user_pending_backtest,
                    "currently_backtesting": user_currently_backtesting,
                },
                "brain_generated": {
                    "total": brain_total,
                    "active": brain_active,
                    "pending_backtest": brain_pending_backtest,
                    "currently_backtesting": brain_currently_backtesting,
                },
            },
            trading={
                "brain_strategies": {
                    "pnl": brain_pnl,
                    "sharpe": brain_sharpe,
                    "drawdown": brain_drawdown,
                },
                "user_strategies": {
                    "pnl": user_pnl,
                    "sharpe": user_sharpe,
                    "drawdown": user_drawdown,
                },
            },
            revenue={
                "subscriptions": total_subscription_mrr,
                "royalties": total_royalties,
                "platform_fees": total_platform_fees,
            },
            top_strategies={
                "most_used": top_used_list,
                "by_sharpe": top_sharpe_list,
                "by_profit": top_profit_list,
                "by_drawdown": top_drawdown_list,
            },
            system={
                "market_data_provider_status": market_data_provider_status,
                "evolution_worker_status": evolution_worker_status,
                "db_status": db_status,
                "redis_status": redis_status,
                "error_count_last_24h": error_count_last_24h,
            },
        )
        
        # Cache the result
        cache.set("admin_metrics_summary", result, user_id, ttl_seconds=30)
        
        return result
    except Exception as e:
        # Return safe fallback on error
        import traceback
        traceback.print_exc()
        return MetricsSummaryResponse(
            users={"total": 0, "active": 0, "current_month_by_tier": {"basic": 0, "pro": 0, "creator": 0}},
            strategies={"total_active": 0, "pending_backtest": 0, "currently_backtesting": 0, "brain": {}, "user": {}},
            trading={"total_pnl": 0.0, "total_sharpe": 0.0, "total_drawdown": 0.0},
            revenue={"subscriptions": 0.0, "royalties": 0.0, "platform_fees": 0.0},
            top_strategies={"most_used": [], "by_sharpe": [], "by_profit": [], "by_drawdown": []},
            system={"error": str(e)}
        )

