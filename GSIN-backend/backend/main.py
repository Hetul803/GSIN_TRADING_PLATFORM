# backend/main.py
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from typing import List
from fastapi import Query
from contextlib import asynccontextmanager

import asyncio
import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.health import health_router
from backend.api.mcn_endpoints import mcn_router
from backend.api.users import router as users_router
from backend.api.subscriptions import router as subscriptions_router
from backend.api.groups import router as groups_router
from backend.api.trades import router as trades_router
from backend.api.trading_settings import router as trading_settings_router
from backend.api.paper_account import router as paper_account_router
from backend.api.auth import router as auth_router
from backend.api.feedback import router as feedback_router
from backend.api.admin import router as admin_router
from backend.api.admin_settings import router as admin_settings_router  # PHASE 2
from backend.api.admin_promo import router as admin_promo_router  # PHASE 2
from backend.api.admin_metrics import router as admin_metrics_router  # PHASE 2
from backend.api.admin_health import router as admin_health_router  # PHASE 2
from backend.api.notifications import router as notifications_router
from backend.market_data import market_router
from backend.market_data import asset_router
from backend.market_data.finnhub_webhook import router as finnhub_webhook_router
from backend.strategy_engine import router as strategy_router
from backend.brain import router as brain_router
from backend.brain.brain_summary import router as brain_summary_router
from backend.broker import router as broker_router
from backend.api.worker import router as worker_router
from backend.api.system import router as system_router
from backend.api.system_health import router as system_health_router
# PHASE 1: Use rewritten WebSocket that never crashes
from backend.api.websocket_rewrite import router as websocket_router  # PHASE 4
from backend.api.royalties import router as royalties_router  # PHASE 5
from backend.api.fees import router as fees_router  # FIX 5: Fee calculation endpoints
from backend.api.tutorial import router as tutorial_router  # PHASE 5
from backend.api.compliance import router as compliance_router  # PHASE 5
from backend.api.broker_connect import router as broker_connect_router  # PHASE 6
from backend.api.dev import router as dev_router  # FINAL ALIGNMENT
from backend.api.metrics import router as metrics_router  # PHASE 7: Metrics
from backend.api.agreements import router as agreements_router  # User agreements (Terms, Privacy, Risk Disclosure)
from backend.api.monitoring import router as monitoring_router  # Monitoring endpoints
from backend.utils.logger import log
from backend.utils.sentry_setup import init_sentry
from backend.middleware.jwt_auth import JWTAuthMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware  # PHASE 6
from backend.middleware.rate_limiter import RateLimitMiddleware  # PHASE 6
from backend.middleware.request_signing import RequestSigningMiddleware  # PHASE 6
from backend.middleware.royalty_lock import RoyaltyLockMiddleware  # PHASE 4: Royalty lock
# PHASE 4: Legacy code removed - REGISTRY and feedback_loop no longer used
# Evolution Worker handles all strategy processing
from backend.db.session import engine, get_db
from backend.db.models import Base, UserStrategy
from backend.db.session import SessionLocal
from backend.workers.evolution_worker import run_evolution_worker_loop, EvolutionWorker
from backend.strategy_engine.seed_loader import load_seed_strategies
from pathlib import Path
import threading
try:
    import MemoryClusterNetworks as mcn  # this is the folder/package you installed with pip -e
    MCN_AVAILABLE = True
except ImportError:
    mcn = None
    MCN_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Validate environment variables
    from backend.utils.env_validator import validate_env_vars, print_env_validation
    env_validation = validate_env_vars()
    print_env_validation(env_validation)
    
    # Initialize Sentry error monitoring
    init_sentry()
    
    # Initialize Redis client (for caching and distributed locks)
    try:
        from backend.utils.redis_client import get_redis_client
        redis_client = get_redis_client()
        if redis_client.is_available:
            log("✅ Redis initialized and connected")
        else:
            log("⚠️  Redis not available - using in-memory fallback")
    except Exception as e:
        log(f"⚠️  Redis initialization error: {e} - using in-memory fallback")
    
    # create tables
    Base.metadata.create_all(bind=engine)
    
    # PHASE 4: Legacy scheduler removed - Evolution Worker handles all processing
    # asyncio.create_task(scheduler())
    
    # TASK 1 FIX: Initialize market data providers (historical vs live separation)
    from backend.market_data.market_data_provider import _initialize_providers
    _initialize_providers()
    
    # TWELVE DATA INTEGRATION: Run Twelve Data sanity check for common symbols
    try:
        from backend.market_data.market_data_provider import get_historical_provider
        from datetime import datetime, timedelta, timezone
        
        historical_provider = get_historical_provider()
        if historical_provider:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=180)  # 6 months
            
            test_symbols = ["AAPL", "MSFT", "SPY"]
            provider_name = historical_provider.__class__.__name__
            
            all_passed = True
            for symbol in test_symbols:
                try:
                    # Try to get candles using the provider's interface
                    if hasattr(historical_provider, "get_historical_ohlcv"):
                        df = historical_provider.get_historical_ohlcv(symbol, "1d", start_date, end_date)
                    elif hasattr(historical_provider, "get_candles"):
                        candles = historical_provider.get_candles(symbol, "1d", limit=180, start=start_date, end=end_date)
                        import pandas as pd
                        if candles:
                            df = pd.DataFrame([{"open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume} for c in candles])
                        else:
                            df = pd.DataFrame()
                    else:
                        print(f"⚠️  {provider_name} does not support historical OHLCV")
                        all_passed = False
                        continue
                    
                    if df.empty or len(df) == 0:
                        print(f"⚠️  {provider_name} sanity check: {symbol}/1d returned no data")
                        all_passed = False
                    else:
                        print(f"✅ {provider_name} sanity check passed for {symbol}/1d: {len(df)} candles")
                except Exception as e:
                    print(f"⚠️  {provider_name} sanity check failed for {symbol}/1d: {e}")
                    all_passed = False
            
            if all_passed:
                print(f"✅ {provider_name} sanity check passed for all test symbols")
            else:
                print(f"⚠️  {provider_name} sanity check failed for one or more symbols (non-fatal)")
        else:
            print("⚠️  No historical provider available for sanity check (non-fatal)")
    except Exception as e:
        print(f"⚠️  Historical provider sanity check error (non-fatal): {e}")
    
    # Load seed strategies - always try to load missing ones (seed_loader handles deduplication)
    try:
        db = next(get_db())
        try:
            strategy_count = db.query(UserStrategy).count()
            log(f"[GSIN] Found {strategy_count} existing strategies")
            
            # Always try to load seed strategies (seed_loader will skip duplicates)
            # This ensures all 45 strategies (5 individual + 40 from proven_strategies.json) are loaded
            seed_dir = Path(__file__).resolve().parents[1] / "seed_strategies"
            if seed_dir.exists() or (Path(__file__).resolve().parents[2] / "seed_strategies").exists():
                log("[GSIN] Loading seed strategies (duplicates will be skipped)...")
                loaded = load_seed_strategies(db, seed_dir)
                if loaded > 0:
                    log(f"[GSIN] Loaded {loaded} new seed strategies")
                else:
                    log(f"[GSIN] All seed strategies already exist (deduplication)")
            else:
                log(f"[GSIN] Seed strategies directory not found, skipping seed load")
            
            # Activate existing strategies that might not be active
            try:
                from backend.scripts.activate_existing_strategies import activate_existing_strategies
                activated = activate_existing_strategies()
                if activated > 0:
                    log(f"[GSIN] Activated {activated} existing strategies for evolution")
            except Exception as e:
                log(f"[GSIN] Warning: Could not activate existing strategies: {e}")
        except Exception as e:
            log(f"[GSIN] Error loading seed strategies: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    except Exception as e:
        log(f"[GSIN] Error checking for seed strategies: {e}")
    
    # PHASE 4: Prewarm cache for popular symbols
    try:
        from backend.market_data.cache import get_cache
        cache = get_cache()
        popular_symbols = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY", "QQQ", "BTCUSD", "ETHUSD"]
        log("[GSIN] Prewarming cache for popular symbols...")
        # Run in background thread to not block startup
        def prewarm_cache():
            cache.prewarm_symbols(popular_symbols, timeframe="1d", limit=100)
        prewarm_thread = threading.Thread(target=prewarm_cache, daemon=True)
        prewarm_thread.start()
    except Exception as e:
        log(f"[GSIN] Cache prewarming failed: {e}")
    
    # Start evolution worker in background thread
    def start_evolution_worker():
        """Start evolution worker in a separate thread with auto-restart on crash."""
        while True:
            try:
                log("[GSIN] Starting evolution worker...")
                run_evolution_worker_loop()
            except Exception as e:
                log(f"[GSIN] Evolution worker crashed: {e}")
                import traceback
                traceback.print_exc()
                log("[GSIN] Evolution worker will restart in 60 seconds...")
                import time
                time.sleep(60)  # Wait 60 seconds before restarting
    
    evolution_thread = threading.Thread(target=start_evolution_worker, daemon=True)
    evolution_thread.start()
    log("[GSIN] Evolution worker thread started")
    
    # Start Monitoring Worker
    def start_monitoring_worker():
        """Start the monitoring worker in a background thread."""
        from backend.workers.monitoring_worker import run_monitoring_worker_loop
        run_monitoring_worker_loop()
    
    monitoring_thread = threading.Thread(target=start_monitoring_worker, daemon=True)
    monitoring_thread.start()
    log("[GSIN] Monitoring worker thread started")
    
    yield  # App is running
    
    # Shutdown (if needed)
    # Evolution worker thread is daemon, so it will exit when main process exits


def create_app() -> FastAPI:
    app = FastAPI(
        title="GSIN Backend API",
        version="0.3.0",
        description="GSIN Trading Platform Backend API - Strategy Engine, Brain AI, Market Data, and Trading Execution",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    app.include_router(router)
    app.include_router(health_router)
    app.include_router(mcn_router)
    app.include_router(users_router)
    app.include_router(subscriptions_router, prefix="/api")
    app.include_router(groups_router, prefix="/api")  # Fixed: Add /api prefix
    app.include_router(trades_router)
    app.include_router(trading_settings_router, prefix="/api")
    app.include_router(paper_account_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(admin_settings_router, prefix="/api")  # PHASE 2
    app.include_router(admin_promo_router, prefix="/api")  # PHASE 2
    app.include_router(admin_metrics_router, prefix="/api")  # PHASE 2
    app.include_router(admin_health_router, prefix="/api")  # PHASE 2
    app.include_router(notifications_router, prefix="/api")
    app.include_router(market_router.router, prefix="/api")
    app.include_router(asset_router.router, prefix="/api")
    app.include_router(finnhub_webhook_router, prefix="/api")  # FINNHUB: Webhook handler
    app.include_router(strategy_router, prefix="/api")
    app.include_router(brain_router, prefix="/api")
    app.include_router(brain_summary_router, prefix="/api")
    app.include_router(broker_router, prefix="/api")
    app.include_router(worker_router, prefix="/api")
    app.include_router(system_router, prefix="/api")
    app.include_router(system_health_router, prefix="/api")
    app.include_router(websocket_router, prefix="/api")  # PHASE 4: WebSocket support
    app.include_router(royalties_router, prefix="/api")  # PHASE 5: Royalties
    app.include_router(fees_router, prefix="/api")  # FIX 5: Fee calculation endpoints
    app.include_router(tutorial_router, prefix="/api")  # PHASE 5: Tutorial
    app.include_router(compliance_router)  # PHASE 5: Privacy, Terms, Disclaimer (no /api prefix for public access)
    app.include_router(agreements_router, prefix="/api")  # User agreements (Terms, Privacy, Risk Disclosure)
    app.include_router(broker_connect_router, prefix="/api")  # PHASE 6: Broker connection
    app.include_router(dev_router, prefix="/api")  # FINAL ALIGNMENT: Dev endpoints
    app.include_router(metrics_router, prefix="/api")  # PHASE 7: Metrics endpoint
    app.include_router(monitoring_router, prefix="/api")  # Monitoring endpoints

    # ISSUE 4 FIX: CORS middleware (FIRST - must handle OPTIONS requests before other middleware)
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],  # ISSUE 4 FIX: Allow all methods including OPTIONS
        allow_headers=["*"],  # ISSUE 4 FIX: Allow all headers
        max_age=3600,
    )
    
    # PHASE 6: Security middleware (order matters - security headers after CORS)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)  # PHASE 6: Rate limiting
    app.add_middleware(RequestSigningMiddleware)  # Optional - can be disabled for development
    
    # Add JWT authentication middleware (must be before RoyaltyLockMiddleware)
    app.add_middleware(JWTAuthMiddleware)
    
    # PHASE 4: Royalty lock middleware (after JWT so we have user_id)
    app.add_middleware(RoyaltyLockMiddleware)
    
    return app

app = create_app()

# PHASE 4: Legacy scheduler removed - Evolution Worker handles all strategy processing
# The Evolution Worker runs continuously and processes all active strategies
# Legacy imports commented out:
# from backend.core.registry import REGISTRY
# from backend.finance.backtester import run_backtest
# from backend.core.feedback_loop import feedback_after_backtest
# Startup logic moved to lifespan() function above

if __name__ == "__main__":
    log("Starting GSIN Backend at http://localhost:8000 ...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

