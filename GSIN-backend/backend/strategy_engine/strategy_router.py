# backend/strategy_engine/strategy_router.py
"""
Strategy Engine API router.
Handles strategy CRUD, backtesting, mutation, and signal generation.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import AssetType
from .strategy_models import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
    BacktestRequest,
    BacktestResponse,
    MutationResponse,
    SignalResponse,
)
from .strategy_schema import StrategyBuilderRequest
from .backtest_engine import BacktestEngine
from .mutation_engine import MutationEngine
from .strategy_service import StrategyService
from .scoring import score_strategy
from .validation import validate_strategy_create

router = APIRouter(prefix="/strategies", tags=["strategies"])


# PHASE 4: JWT-only authentication - use dependency directly


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    strategy_data: StrategyCreateRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Create a new strategy.
    
    Requires USER_PLUS_UPLOAD or CREATOR subscription plan.
    
    Validates that strategy includes:
    - ticker/symbol (single or multiple)
    - timeframe
    - entry rules
    - exit rules
    """
    # Check subscription - strategy upload requires USER_PLUS_UPLOAD or CREATOR
    sub_info = crud.get_user_subscription_info(db, user_id)
    if not sub_info or not sub_info.get("can_upload_strategies", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Strategy upload requires USER_PLUS_UPLOAD or CREATOR subscription. Please upgrade your plan."
        )
    
    # PHASE 3: Prefer builder format if provided
    if strategy_data.builder_request:
        # Use structured builder format
        builder = strategy_data.builder_request
        normalized_ruleset = builder.to_ruleset()
        parameters = builder.to_parameters()
        description = builder.description or strategy_data.description
        asset_type = builder.asset_type
    else:
        # Legacy format - validate and normalize
        if not strategy_data.ruleset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'builder_request' or 'ruleset' must be provided. Please use the Strategy Builder UI."
            )
        
        # Validate strategy before creating
        validate_strategy_create(
            name=strategy_data.name,
            ruleset=strategy_data.ruleset,
            parameters=strategy_data.parameters
        )
        
        # AUTO-INFER: Normalize and auto-infer rules if needed
        from .strategy_normalizer import normalize_strategy_ruleset, auto_infer_rules_for_user_strategy
        
        # Check if ruleset needs inference (missing entry_conditions/exit_rules)
        raw_ruleset = strategy_data.ruleset or {}
        has_entry = bool(raw_ruleset.get("entry_conditions") or raw_ruleset.get("entry_rules") or raw_ruleset.get("entry") or raw_ruleset.get("conditions"))
        has_exit = bool(raw_ruleset.get("exit_rules") or raw_ruleset.get("exit_conditions") or raw_ruleset.get("exit") or raw_ruleset.get("stop_loss") or raw_ruleset.get("take_profit"))
        
        if not has_entry or not has_exit:
            # Auto-infer rules from description/parameters
            normalized_ruleset = auto_infer_rules_for_user_strategy(
                name=strategy_data.name,
                description=strategy_data.description or "",
                parameters=strategy_data.parameters or {},
                simple_ruleset=raw_ruleset
            )
        else:
            # Normalize existing ruleset
            normalized_ruleset = normalize_strategy_ruleset(raw_ruleset)
        
        parameters = strategy_data.parameters or {}
        description = strategy_data.description
        asset_type = strategy_data.asset_type
    
    strategy = crud.create_user_strategy(
        db=db,
        user_id=user_id,
        name=strategy_data.name,
        description=description,
        parameters=parameters,
        ruleset=normalized_ruleset,
        asset_type=asset_type,
    )
    
    return StrategyResponse(
        id=strategy.id,
        user_id=strategy.user_id,
        name=strategy.name,
        description=strategy.description,
        parameters=strategy.parameters,
        ruleset=strategy.ruleset,
        asset_type=strategy.asset_type.value,
        score=strategy.score,
        last_backtest_at=strategy.last_backtest_at,
        last_backtest_results=strategy.last_backtest_results,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


@router.get("", response_model=List[StrategyResponse])
async def list_strategies(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    active_only: bool = False,
    ticker: Optional[str] = Query(None, description="Filter by ticker/symbol (e.g., AAPL)"),
    min_capital: Optional[float] = Query(None, description="Minimum capital required"),
    max_capital: Optional[float] = Query(None, description="Maximum capital required"),
    min_winrate: Optional[float] = Query(None, ge=0, le=1, description="Minimum winrate (0-1)"),
    min_sharpe: Optional[float] = Query(None, description="Minimum Sharpe ratio"),
    risk_level: Optional[str] = Query(None, description="Risk level: conservative, moderate, aggressive")
):
    """
    List strategies for the current user with optional filters.
    
    PHASE 2: Added search by ticker, budget, winrate, sharpe, risk level.
    """
    # ISSUE 5 FIX: Handle case where no strategies exist
    try:
        strategies = crud.list_user_strategies(
            db, user_id, 
            active_only=active_only,
            ticker=ticker,
            min_capital=min_capital,
            max_capital=max_capital,
            min_winrate=min_winrate,
            min_sharpe=min_sharpe,
            risk_level=risk_level
        )
    except Exception as e:
        # Log error but return empty list instead of crashing
        print(f"⚠️  Error listing strategies for user {user_id}: {e}")
        strategies = []
    
    # PHASE 2: Calculate confidence scores and Brain reasons for each strategy
    from ..brain.recommended_strategies import RecommendedStrategiesService
    from ..brain.explanation_engine import ExplanationEngine
    recommended_service = RecommendedStrategiesService()
    explanation_engine = ExplanationEngine()
    
    responses = []
    for s in strategies:
        # Calculate confidence score from backtest results
        confidence_score = None
        brain_reason = None
        
        if s.last_backtest_results:
            # Extract metrics
            winrate = s.last_backtest_results.get("win_rate", 0.0)
            sharpe = s.last_backtest_results.get("sharpe_ratio", 0.0)
            sample_size = s.last_backtest_results.get("total_trades", 0)
            avg_rr = s.last_backtest_results.get("avg_rr", 1.0)
            
            # Calculate confidence based on metrics
            base_confidence = (winrate * 0.6) + (min(avg_rr / 3.0, 1.0) * 0.4)
            sample_adjustment = min(1.0, sample_size / 100.0)
            confidence_score = base_confidence * (0.5 + 0.5 * sample_adjustment)
            confidence_score = min(1.0, max(0.0, confidence_score))
            
            # Generate Brain explanation
            try:
                brain_reason = explanation_engine.explain_strategy_recommendation(
                    strategy_name=s.name,
                    winrate=winrate,
                    sharpe=sharpe,
                    sample_size=sample_size,
                    avg_rr=avg_rr
                )
            except Exception as e:
                print(f"Error generating explanation: {e}")
                brain_reason = f"Strategy with {winrate:.1%} winrate and {sharpe:.2f} Sharpe ratio"
        
        # PHASE 1: Generate explanation if missing
        explanation_human = s.explanation_human
        risk_note = s.risk_note
        if not explanation_human and s.ruleset:
            from .strategy_explanation import generate_human_explanation
            stats = s.last_backtest_results or {}
            explanation_human, risk_note = generate_human_explanation(
                {"name": s.name, "ruleset": s.ruleset, "asset_type": s.asset_type.value},
                stats
            )
        
        responses.append(
            StrategyResponse(
                id=s.id,
                user_id=s.user_id,
                name=s.name,
                description=s.description,
                parameters=s.parameters,
                ruleset=s.ruleset,
                asset_type=s.asset_type.value,
                score=s.score,
                confidence_score=confidence_score,  # PHASE 2: Added
                brain_reason=brain_reason,  # PHASE 2: Added
                explanation_human=explanation_human,  # PHASE 1: Added
                risk_note=risk_note,  # PHASE 1: Added
                last_backtest_at=s.last_backtest_at,
                last_backtest_results=s.last_backtest_results,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    
    return responses


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get a strategy by ID."""
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    return StrategyResponse(
        id=strategy.id,
        user_id=strategy.user_id,
        name=strategy.name,
        description=strategy.description,
        parameters=strategy.parameters,
        ruleset=strategy.ruleset,
        asset_type=strategy.asset_type.value,
        score=strategy.score,
        last_backtest_at=strategy.last_backtest_at,
        last_backtest_results=strategy.last_backtest_results,
        is_active=strategy.is_active,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


@router.get("/{strategy_id}/tearsheet")
async def get_strategy_tearsheet(
    strategy_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    # Cache expensive tearsheet calculation (5 minute TTL - tearsheet doesn't change often)
    from ..utils.response_cache import get_cache
    cache = get_cache()
    
    cached_result = cache.get("strategy_tearsheet", strategy_id, ttl_seconds=300)
    if cached_result is not None:
        return cached_result
    """Get comprehensive strategy tear sheet with all metrics and MCN analysis."""
    from datetime import datetime, timedelta, timezone
    from ..db.models import User, StrategyLineage, UserStrategy
    from ..brain.mcn_adapter import get_mcn_adapter
    from ..strategy_engine.scoring import calculate_sortino_ratio
    import statistics
    
    # Allow viewing any active strategy (for marketplace), not just owned ones
    strategy = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Only check ownership for private strategies
    if not strategy.is_active and strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Get creator info
    creator = crud.get_user_by_id(db, strategy.user_id)
    creator_name = creator.name if creator else "Unknown"
    if strategy.evolution_attempts > 0:
        creator_name = "GSIN Brain"
    
    # Get backtest results
    backtest_results = strategy.last_backtest_results or {}
    equity_curve = backtest_results.get("equity_curve", [])
    
    # Calculate basic metrics
    total_return = backtest_results.get("total_return", 0.0)
    win_rate = backtest_results.get("win_rate", 0.0)
    max_drawdown = backtest_results.get("max_drawdown", 0.0)
    sharpe_ratio = backtest_results.get("sharpe_ratio", 0.0)
    total_trades = backtest_results.get("total_trades", 0)
    avg_pnl = backtest_results.get("avg_pnl", 0.0)
    profit_factor = backtest_results.get("profit_factor", 0.0)
    
    # Calculate annualized return
    annualized_return = 0.0
    if strategy.last_backtest_at and equity_curve:
        try:
            # Estimate period from equity curve
            if len(equity_curve) >= 2:
                start_date = datetime.fromisoformat(equity_curve[0].get("timestamp", "").replace("Z", "+00:00")) if isinstance(equity_curve[0].get("timestamp"), str) else strategy.last_backtest_at
                end_date = datetime.fromisoformat(equity_curve[-1].get("timestamp", "").replace("Z", "+00:00")) if isinstance(equity_curve[-1].get("timestamp"), str) else datetime.now(timezone.utc)
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                
                days = (end_date - start_date).days
                if days > 0:
                    years = days / 365.25
                    annualized_return = ((1 + total_return / 100.0) ** (1 / years) - 1) * 100 if years > 0 else 0.0
        except:
            pass
    
    # Calculate Sortino ratio
    sortino_ratio = backtest_results.get("sortino_ratio")
    if not sortino_ratio and equity_curve:
        try:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1].get("equity", 10000) if isinstance(equity_curve[i-1], dict) else equity_curve[i-1]
                curr_equity = equity_curve[i].get("equity", 10000) if isinstance(equity_curve[i], dict) else equity_curve[i]
                if prev_equity > 0:
                    returns.append((curr_equity - prev_equity) / prev_equity)
            sortino_ratio = calculate_sortino_ratio(returns) if returns else None
        except:
            pass
    
    # Calculate max drawdown normalized ($10,000 account)
    max_drawdown_normalized = (max_drawdown / 100.0) * 10000.0 if max_drawdown else 0.0
    
    # Calculate longest drawdown duration
    longest_drawdown_duration = "N/A"
    if equity_curve:
        try:
            peak = equity_curve[0].get("equity", 10000) if isinstance(equity_curve[0], dict) else equity_curve[0]
            drawdown_start = None
            max_dd_duration = 0
            current_dd_duration = 0
            
            for point in equity_curve:
                equity = point.get("equity", 10000) if isinstance(point, dict) else point
                if equity > peak:
                    peak = equity
                    drawdown_start = None
                    current_dd_duration = 0
                elif equity < peak * 0.99:  # 1% drawdown threshold
                    if drawdown_start is None:
                        drawdown_start = point.get("timestamp") if isinstance(point, dict) else None
                    current_dd_duration += 1
                    max_dd_duration = max(max_dd_duration, current_dd_duration)
            
            if max_dd_duration > 0:
                longest_drawdown_duration = f"{max_dd_duration} days"
        except:
            pass
    
    # Calculate trades per month (based on backtest period)
    trades_per_month = 0.0
    if equity_curve and total_trades > 0:
        try:
            if len(equity_curve) >= 2:
                start_date = equity_curve[0].get("timestamp") if isinstance(equity_curve[0], dict) else None
                end_date = equity_curve[-1].get("timestamp") if isinstance(equity_curve[-1], dict) else None
                if start_date and end_date:
                    try:
                        start = datetime.fromisoformat(str(start_date).replace("Z", "+00:00"))
                        end = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
                        days = (end - start).days
                        if days > 0:
                            months = days / 30.0
                            trades_per_month = total_trades / months if months > 0 else 0.0
                    except:
                        pass
        except:
            pass
    
    # Calculate average time in trade (simplified)
    avg_time_in_trade = "N/A"
    if equity_curve and total_trades > 0:
        try:
            if len(equity_curve) > 1:
                start_date = equity_curve[0].get("timestamp") if isinstance(equity_curve[0], dict) else None
                end_date = equity_curve[-1].get("timestamp") if isinstance(equity_curve[-1], dict) else None
                if start_date and end_date:
                    try:
                        start = datetime.fromisoformat(str(start_date).replace("Z", "+00:00"))
                        end = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
                        total_days = (end - start).days
                        avg_days = total_days / total_trades if total_trades > 0 else 0
                        avg_time_in_trade = f"{avg_days:.1f} days"
                    except:
                        pass
        except:
            pass
    
    # Calculate average win and loss
    avg_win = backtest_results.get("avg_win", 0.0)
    avg_loss = backtest_results.get("avg_loss", 0.0)
    if not avg_win or avg_win == 0:
        # Try to calculate from trades if available
        trades = backtest_results.get("trades", [])
        if trades:
            winning_pnls = [t.get("pnl", 0) for t in trades if isinstance(t, dict) and t.get("pnl", 0) > 0]
            if winning_pnls:
                # Convert percentage to dollar amount (assuming $10,000 account)
                avg_win = statistics.mean([(p / 100.0) * 10000.0 for p in winning_pnls])
    if not avg_loss or avg_loss == 0:
        trades = backtest_results.get("trades", [])
        if trades:
            losing_pnls = [t.get("pnl", 0) for t in trades if isinstance(t, dict) and t.get("pnl", 0) < 0]
            if losing_pnls:
                avg_loss = abs(statistics.mean([(p / 100.0) * 10000.0 for p in losing_pnls]))
    
    # Get MCN analysis
    mcn_adapter = get_mcn_adapter()
    mcn_robustness_score = 50  # Default
    mcn_regime_stability = {"bull": "unknown", "bear": "unknown", "highVol": "unknown", "lowVol": "unknown"}
    mcn_overfitting_risk = "Unknown"
    mcn_novelty_score = 50  # Default
    mcn_lineage = "No lineage data"
    
    try:
        # Get lineage
        parent_lineages = crud.get_strategy_lineages_by_child(db, strategy_id)
        if parent_lineages:
            parent = parent_lineages[0]
            parent_strategy = crud.get_user_strategy(db, parent.parent_strategy_id)
            if parent_strategy:
                mcn_lineage = f"Mutated from '{parent_strategy.name}'"
        
        # Get MCN memory for strategy
        lineage_memory = mcn_adapter.get_strategy_lineage_memory(strategy_id, db)
        if lineage_memory:
            ancestor_stability = lineage_memory.get("ancestor_stability", 0.5)
            mcn_robustness_score = int(ancestor_stability * 100)
            has_overfit = lineage_memory.get("has_overfit_ancestors", False)
            mcn_overfitting_risk = "High" if has_overfit else "Low"
        
        # Get regime context (simplified - would need actual regime testing)
        # For now, use strategy's per_symbol_performance if available
        if strategy.per_symbol_performance:
            # Check performance across different market conditions
            # This is simplified - real implementation would test in different regimes
            mcn_regime_stability = {
                "bull": "pass" if strategy.score and strategy.score > 0.7 else "unknown",
                "bear": "pass" if strategy.score and strategy.score > 0.6 else "unknown",
                "highVol": "unknown",
                "lowVol": "pass" if strategy.score and strategy.score > 0.65 else "unknown"
            }
        
        # Novelty score (based on evolution attempts - fewer attempts = more novel)
        if strategy.evolution_attempts == 0:
            mcn_novelty_score = 95
        elif strategy.evolution_attempts < 3:
            mcn_novelty_score = 85
        elif strategy.evolution_attempts < 5:
            mcn_novelty_score = 70
        else:
            mcn_novelty_score = 50
    except Exception as e:
        print(f"Error getting MCN data: {e}")
    
    # Format equity curve with benchmark (SPY)
    equity_curve_formatted = []
    benchmark_value = 10000.0
    strategy_start_value = equity_curve[0].get("equity", 10000) if equity_curve and isinstance(equity_curve[0], dict) else (equity_curve[0] if equity_curve else 10000)
    
    for i, point in enumerate(equity_curve):
        equity = point.get("equity", 10000) if isinstance(point, dict) else point
        timestamp = point.get("timestamp") if isinstance(point, dict) else None
        
        # Format timestamp
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y-%m-%d")
                else:
                    formatted_date = timestamp.strftime("%Y-%m-%d") if hasattr(timestamp, 'strftime') else str(timestamp)
            except:
                formatted_date = f"2024-01-{i+1:02d}"
        else:
            formatted_date = f"2024-01-{i+1:02d}"
        
        # Calculate benchmark (SPY ~10% annual return, compounded daily)
        if i > 0:
            # Calculate days since start for proper compounding
            try:
                if isinstance(timestamp, str):
                    current_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif hasattr(timestamp, 'isoformat'):
                    current_dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                else:
                    current_dt = datetime.now(timezone.utc)
                
                start_dt = datetime.fromisoformat(str(equity_curve[0].get("timestamp", "")).replace("Z", "+00:00")) if isinstance(equity_curve[0].get("timestamp"), str) else datetime.now(timezone.utc)
                days = (current_dt - start_dt).days
                # 10% annual = (1.10)^(1/365) - 1 daily
                daily_return = (1.10 ** (1/365.25)) - 1
                benchmark_value = 10000.0 * ((1 + daily_return) ** days)
            except:
                # Fallback: simple linear growth
                benchmark_value *= 1.00038  # ~0.038% daily
        
        equity_curve_formatted.append({
            "date": formatted_date,
            "value": equity,
            "benchmark": benchmark_value
        })
    
    return {
        "strategyName": strategy.name,
        "creatorName": creator_name,
        "annualizedReturn": round(annualized_return, 2),
        "sharpeRatio": round(sharpe_ratio, 2) if sharpe_ratio else 0.0,
        "maxDrawdown": round(max_drawdown, 2),
        "totalTrades": total_trades,
        "totalReturn": round(total_return, 2),
        "winRate": round(win_rate * 100, 2),
        "profitFactor": round(profit_factor, 2) if profit_factor else 0.0,
        "equityCurve": equity_curve_formatted,
        "benchmarkSymbol": "SPY",
        "sortinoRatio": round(sortino_ratio, 2) if sortino_ratio else 0.0,
        "maxDrawdownNormalized": round(max_drawdown_normalized, 2),
        "longestDrawdownDuration": longest_drawdown_duration,
        "mcnRobustnessScore": mcn_robustness_score,
        "mcnRegimeStability": mcn_regime_stability,
        "mcnOverfittingRisk": mcn_overfitting_risk,
        "mcnNoveltyScore": mcn_novelty_score,
        "mcnLineage": mcn_lineage,
        "tradesPerMonth": round(trades_per_month, 2),
        "avgTimeInTrade": avg_time_in_trade,
        "avgWin": round(avg_win, 2),
        "avgLoss": round(avg_loss, 2),
    }
    
    # Cache the result
    cache.set("strategy_tearsheet", result, strategy_id, ttl_seconds=300)
    
    return result


@router.get("/{strategy_id}/transparency")
async def get_strategy_transparency(
    strategy_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    account_balance: float = Query(10000.0, description="User's account balance for risk calculations"),
    user_risk_profile: str = Query("moderate", description="User's risk profile: low, moderate, high")
):
    """
    Get comprehensive transparency and risk disclosure report for a strategy.
    
    This endpoint provides:
    - Market regime fit analysis
    - Investment requirements (amount, duration)
    - Possible loss scenarios (worst-case, typical)
    - Possible profit scenarios (best-case, typical)
    - Risk metrics and disclosures
    - Suitability warnings
    
    This ensures users make informed decisions before investing.
    """
    from .strategy_transparency import StrategyTransparencyEngine
    from ..db.models import UserStrategy
    
    # Get strategy
    strategy = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Only check ownership for private strategies
    if not strategy.is_active and strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Get strategy ruleset and backtest results
    strategy_dict = {
        "id": strategy.id,
        "name": strategy.name,
        "ruleset": strategy.ruleset,
        "parameters": strategy.parameters
    }
    
    backtest_results = strategy.last_backtest_results or {}
    
    # Get primary symbol from strategy
    symbols = strategy.ruleset.get("symbols", []) if isinstance(strategy.ruleset, dict) else []
    symbol = symbols[0] if symbols else "AAPL"  # Default
    
    # Generate transparency report
    transparency_engine = StrategyTransparencyEngine()
    report = transparency_engine.generate_transparency_report(
        strategy=strategy_dict,
        strategy_id=strategy_id,
        symbol=symbol,
        backtest_results=backtest_results,
        account_balance=account_balance,
        user_risk_profile=user_risk_profile
    )
    
    # Convert to dict for JSON response
    return {
        "current_regime": report.current_regime,
        "regime_fit_score": report.regime_fit_score,
        "regime_stability": report.regime_stability,
        "recommended_investment_min": report.recommended_investment_min,
        "recommended_investment_max": report.recommended_investment_max,
        "typical_investment": report.typical_investment,
        "expected_duration_days": report.expected_duration_days,
        "expected_trades_per_month": report.expected_trades_per_month,
        "possible_loss_worst_case": report.possible_loss_worst_case,
        "possible_loss_typical": report.possible_loss_typical,
        "possible_profit_best_case": report.possible_profit_best_case,
        "possible_profit_typical": report.possible_profit_typical,
        "max_drawdown": report.max_drawdown,
        "probability_of_loss": report.probability_of_loss,
        "expected_annual_return": report.expected_annual_return,
        "expected_annual_return_range": report.expected_annual_return_range,
        "sharpe_ratio": report.sharpe_ratio,
        "risk_level": report.risk_level,
        "risk_factors": report.risk_factors,
        "suitability_warning": report.suitability_warning,
        "backtest_period": report.backtest_period,
        "number_of_trades_analyzed": report.number_of_trades_analyzed,
        "walk_forward_consistency": report.walk_forward_consistency,
        "overfitting_risk": report.overfitting_risk
    }


@router.get("/{strategy_id}/mutation-tree")
async def get_mutation_tree(
    strategy_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get mutation tree/graph showing how a strategy was mutated from original.
    
    Shows:
    - Complete mutation chain from original to current
    - Similarity scores at each mutation
    - Changes made at each step
    - Royalty eligibility status
    - Before/after comparisons
    """
    from .mutation_visualization import mutation_visualization_engine
    
    # Get mutation tree
    mutation_tree = mutation_visualization_engine.get_mutation_tree(strategy_id, db)
    
    if not mutation_tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found or has no mutation history"
        )
    
    # Check if user owns the original strategy
    if mutation_tree.original_uploader_id != user_id:
        # Check if user owns current strategy
        current_strategy = crud.get_user_strategy(db, strategy_id)
        if not current_strategy or current_strategy.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view mutation tree for your own strategies"
            )
    
    # Convert to dict for JSON response
    return {
        "original_strategy_id": mutation_tree.original_strategy_id,
        "original_strategy_name": mutation_tree.original_strategy_name,
        "original_uploader_id": mutation_tree.original_uploader_id,
        "total_mutations": mutation_tree.total_mutations,
        "current_similarity": mutation_tree.current_similarity,
        "current_royalty_eligible": mutation_tree.current_royalty_eligible,
        "current_royalty_percent": mutation_tree.current_royalty_percent,
        "nodes": [
            {
                "strategy_id": node.strategy_id,
                "strategy_name": node.strategy_name,
                "created_at": node.created_at.isoformat(),
                "similarity_to_original": node.similarity_to_original,
                "mutation_type": node.mutation_type,
                "mutation_params": node.mutation_params,
                "changes_summary": node.changes_summary,
                "royalty_eligible": node.royalty_eligible,
                "royalty_percent": node.royalty_percent,
                "is_brain_generated": node.is_brain_generated
            }
            for node in mutation_tree.nodes
        ]
    }


@router.get("/{strategy_id}/mutation-changes")
async def get_mutation_changes(
    strategy_id: str,
    parent_strategy_id: str = Query(..., description="Parent strategy ID to compare"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get detailed list of changes between parent and child strategy.
    
    Shows exactly what changed:
    - Parameter changes (old value → new value)
    - Rule changes
    - Timeframe changes
    - Symbol changes
    - Indicator changes
    """
    from .mutation_visualization import mutation_visualization_engine
    
    # Verify user has access
    parent = crud.get_user_strategy(db, parent_strategy_id)
    child = crud.get_user_strategy(db, strategy_id)
    
    if not parent or not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if parent.user_id != user_id and child.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view mutation changes for your own strategies"
        )
    
    # Get changes
    changes = mutation_visualization_engine.get_mutation_changes(
        parent_strategy_id,
        strategy_id,
        db
    )
    
    return {
        "parent_strategy_id": parent_strategy_id,
        "parent_strategy_name": parent.name,
        "child_strategy_id": strategy_id,
        "child_strategy_name": child.name,
        "changes": [
            {
                "change_type": change.change_type,
                "field_name": change.field_name,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "impact": change.impact
            }
            for change in changes
        ],
        "total_changes": len(changes)
    }


@router.patch("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    strategy_data: StrategyUpdateRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update a strategy."""
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Convert asset_type string to enum if provided
    asset_type = None
    if strategy_data.asset_type:
        try:
            asset_type = AssetType(strategy_data.asset_type.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid asset_type: {strategy_data.asset_type}"
            )
    
    updated = crud.update_user_strategy(
        db=db,
        strategy_id=strategy_id,
        name=strategy_data.name,
        description=strategy_data.description,
        parameters=strategy_data.parameters,
        ruleset=strategy_data.ruleset,
        asset_type=asset_type,
        is_active=strategy_data.is_active,
    )
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update strategy"
        )
    
    return StrategyResponse(
        id=updated.id,
        user_id=updated.user_id,
        name=updated.name,
        description=updated.description,
        parameters=updated.parameters,
        ruleset=updated.ruleset,
        asset_type=updated.asset_type.value,
        score=updated.score,
        last_backtest_at=updated.last_backtest_at,
        last_backtest_results=updated.last_backtest_results,
        is_active=updated.is_active,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.post("/{strategy_id}/backtest")
async def run_backtest(
    strategy_id: str,
    backtest_data: BacktestRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Run a backtest for a strategy (async - returns immediately with job ID)."""
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Submit backtest to background worker
    from ..workers.backtest_worker import get_backtest_worker
    
    worker = get_backtest_worker()
    job_id = worker.submit_backtest(
        strategy_id=strategy_id,
        user_id=user_id,
        symbol=backtest_data.symbol,
        timeframe=backtest_data.timeframe,
        start_date=backtest_data.start_date,
        end_date=backtest_data.end_date,
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Backtest submitted. Use /api/strategies/backtest/status/{job_id} to check status."
    }


@router.get("/backtest/status/{job_id}")
async def get_backtest_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id_dep),
):
    """Get the status of a backtest job."""
    from ..workers.backtest_worker import get_backtest_worker
    
    worker = get_backtest_worker()
    job_status = worker.get_job_status(job_id, user_id)
    
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest job not found or you don't have access to it"
        )
    
    return job_status
    
    # Record event in MCN (L3)
    from ..brain.mcn_adapter import get_mcn_adapter
    mcn_adapter = get_mcn_adapter()
    mcn_adapter.record_event(
        event_type="strategy_backtest",
        payload={
            "strategy_id": strategy_id,
            "symbol": backtest_data.symbol,
            "timeframe": backtest_data.timeframe,
            "total_return": results["total_return"],
            "win_rate": results["win_rate"],
            "max_drawdown": results["max_drawdown"],
            "score": score,
            "timestamp": datetime.now().isoformat(),
        },
        user_id=user_id,
        strategy_id=strategy_id,
    )
    
    # Calculate equity curve from results
    equity_curve = []
    if "equity_curve" in results:
        equity_curve = results["equity_curve"]
    elif "trades" in results and "candles" in results:
        # Calculate equity curve if not already in results
        equity_curve = engine._calculate_equity_curve(results["trades"], results.get("candles", []))
    
    # Return response with equity curve
    response_data = {
        "id": backtest.id,
        "strategy_id": backtest.strategy_id,
        "symbol": backtest.symbol,
        "timeframe": backtest.timeframe,
        "start_date": backtest.start_date.isoformat(),
        "end_date": backtest.end_date.isoformat(),
        "metrics": {
            "total_return": backtest.total_return,
            "win_rate": backtest.win_rate,
            "max_drawdown": backtest.max_drawdown,
            "avg_pnl": backtest.avg_pnl,
            "num_trades": backtest.total_trades,
        },
        "equity_curve": equity_curve,
        "results": backtest.results,
        "created_at": backtest.created_at.isoformat(),
    }
    
    return response_data


@router.post("/{strategy_id}/mutate", response_model=MutationResponse)
async def mutate_strategy(
    strategy_id: str,
    num_mutations: int = 3,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Create mutated versions of a strategy."""
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Generate mutations
    engine = MutationEngine()
    mutations = engine.mutate_strategy(strategy, num_mutations=min(num_mutations, 3))
    
    # Create mutated strategies
    mutated_strategies = []
    lineage_ids = []
    
    for mutation in mutations:
        mutated_data = mutation["mutated_strategy"]
        new_strategy = crud.create_user_strategy(
            db=db,
            user_id=user_id,
            name=mutated_data["name"],
            description=mutated_data["description"],
            parameters=mutated_data["parameters"],
            ruleset=mutated_data["ruleset"],
            asset_type=mutated_data["asset_type"],
        )
        
        # Create lineage record
        lineage = crud.create_strategy_lineage(
            db=db,
            parent_strategy_id=strategy_id,
            child_strategy_id=new_strategy.id,
            mutation_type=mutation["mutation_type"],
            mutation_params=mutation["mutation_params"],
        )
        
        mutated_strategies.append(StrategyResponse(
            id=new_strategy.id,
            user_id=new_strategy.user_id,
            name=new_strategy.name,
            description=new_strategy.description,
            parameters=new_strategy.parameters,
            ruleset=new_strategy.ruleset,
            asset_type=new_strategy.asset_type.value,
            score=new_strategy.score,
            last_backtest_at=new_strategy.last_backtest_at,
            last_backtest_results=new_strategy.last_backtest_results,
            is_active=new_strategy.is_active,
            created_at=new_strategy.created_at,
            updated_at=new_strategy.updated_at,
        ))
        lineage_ids.append(lineage.id)
    
    # Record event in MCN (L3)
    from ..brain.mcn_adapter import get_mcn_adapter
    mcn_adapter = get_mcn_adapter()
    mcn_adapter.record_event(
        event_type="strategy_mutated",
        payload={
            "parent_strategy_id": strategy_id,
            "num_mutations": len(mutated_strategies),
            "mutation_types": [m["mutation_type"] for m in mutations],
            "timestamp": datetime.now().isoformat(),
        },
        user_id=user_id,
        strategy_id=strategy_id,
    )
    
    return MutationResponse(
        parent_strategy_id=strategy_id,
        mutated_strategies=mutated_strategies,
        lineage_ids=lineage_ids,
    )


@router.get("/{strategy_id}/signal", response_model=SignalResponse)
async def get_signal(
    strategy_id: str,
    symbol: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Generate a trading signal from a strategy."""
    strategy = crud.get_user_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found"
        )
    
    # Check ownership
    if strategy.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this strategy"
        )
    
    # Generate signal
    service = StrategyService()
    try:
        signal = service.generate_signal(
            strategy_id=strategy_id,
            strategy_ruleset=strategy.ruleset,
            strategy_score=strategy.score,
            symbol=symbol,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signal generation failed: {str(e)}"
        )
    
    return SignalResponse(**signal)

