# backend/workers/backtest_worker.py
"""
Background worker for running backtests asynchronously.
Prevents backtests from blocking API requests.
"""
import uuid
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from ..strategy_engine.backtest_engine import BacktestEngine
from ..strategy_engine.scoring import score_strategy
from ..strategy_engine.status_manager import determine_strategy_status, should_discard_strategy
from ..db.session import get_db
from ..db import crud


class BacktestJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BacktestJob:
    """Represents a backtest job."""
    
    def __init__(
        self,
        job_id: str,
        strategy_id: str,
        user_id: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ):
        self.job_id = job_id
        self.strategy_id = strategy_id
        self.user_id = user_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.status = BacktestJobStatus.PENDING
        self.results: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None


class BacktestWorker:
    """Manages background backtest jobs."""
    
    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="backtest")
        self.jobs: Dict[str, BacktestJob] = {}
        self.lock = Lock()
        # Clean up old jobs after 1 hour
        self.job_retention_hours = 1
    
    def submit_backtest(
        self,
        strategy_id: str,
        user_id: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Submit a backtest job and return job ID."""
        job_id = str(uuid.uuid4())
        
        job = BacktestJob(
            job_id=job_id,
            strategy_id=strategy_id,
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        with self.lock:
            self.jobs[job_id] = job
        
        # Submit to executor
        self.executor.submit(self._run_backtest, job)
        
        return job_id
    
    def _run_backtest(self, job: BacktestJob):
        """Run the backtest in background thread."""
        job.status = BacktestJobStatus.RUNNING
        
        try:
            # Get database session
            db = next(get_db())
            try:
                # Get strategy
                strategy = crud.get_user_strategy(db, job.strategy_id)
                if not strategy:
                    raise ValueError(f"Strategy {job.strategy_id} not found")
                
                # Check ownership
                if strategy.user_id != job.user_id:
                    raise ValueError("Strategy does not belong to user")
                
                # Run backtest
                engine = BacktestEngine()
                results = engine.run_backtest(
                    symbol=job.symbol,
                    ruleset=strategy.ruleset,
                    timeframe=job.timeframe,
                    start_date=job.start_date,
                    end_date=job.end_date,
                )
                
                # Calculate score
                score = score_strategy(results, use_test_metrics=True)
                
                # Save backtest record
                backtest = crud.create_strategy_backtest(
                    db=db,
                    strategy_id=job.strategy_id,
                    symbol=job.symbol,
                    timeframe=job.timeframe,
                    start_date=job.start_date,
                    end_date=job.end_date,
                    total_return=results["total_return"],
                    win_rate=results["win_rate"],
                    max_drawdown=results["max_drawdown"],
                    avg_pnl=results["avg_pnl"],
                    total_trades=results["total_trades"],
                    sharpe_ratio=results.get("sharpe_ratio"),
                    results=results,
                )
                
                # Update strategy status
                strategy_dict = {
                    "id": strategy.id,
                    "evolution_attempts": strategy.evolution_attempts or 0,
                    "status": strategy.status or "experiment",
                }
                
                if should_discard_strategy(strategy_dict, results):
                    new_status = "discarded"
                    is_proposable = False
                else:
                    new_status, is_proposable = determine_strategy_status(
                        strategy=strategy_dict,
                        backtest_results=results,
                        current_status=strategy.status or "experiment",
                        db=db  # Pass DB for MCN checks
                    )
                
                # PHASE 1: Generate/update explanation when status changes or backtest completes
                from ..strategy_engine.strategy_explanation import generate_human_explanation
                explanation_human, risk_note = generate_human_explanation(
                    {"name": strategy.name, "ruleset": strategy.ruleset, "asset_type": strategy.asset_type.value},
                    results
                )
                
                # Update strategy
                crud.update_user_strategy(
                    db=db,
                    strategy_id=job.strategy_id,
                    score=score,
                    status=new_status,
                    is_proposable=is_proposable,
                    last_backtest_at=datetime.now(timezone.utc),
                    last_backtest_results=results,
                    train_metrics=results.get("train_metrics"),
                    test_metrics=results.get("test_metrics"),
                    explanation_human=explanation_human,
                    risk_note=risk_note,
                )
                
                db.commit()
                
                # Prepare response
                job.results = {
                    "backtest_id": backtest.id,
                    "strategy_id": job.strategy_id,
                    "symbol": job.symbol,
                    "timeframe": job.timeframe,
                    "total_return": results["total_return"],
                    "win_rate": results["win_rate"],
                    "max_drawdown": results["max_drawdown"],
                    "avg_pnl": results["avg_pnl"],
                    "total_trades": results["total_trades"],
                    "sharpe_ratio": results.get("sharpe_ratio"),
                    "score": score,
                    "equity_curve": results.get("equity_curve", []),
                    "train_metrics": results.get("train_metrics"),
                    "test_metrics": results.get("test_metrics"),
                    "overfitting_detected": results.get("overfitting_detected", False),
                }
                
                job.status = BacktestJobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                
            finally:
                db.close()
                
        except Exception as e:
            job.status = BacktestJobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            import traceback
            traceback.print_exc()
    
    def get_job_status(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get job status. Returns None if job not found or user doesn't own it."""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            
            # Check ownership
            if job.user_id != user_id:
                return None
            
            return {
                "job_id": job.job_id,
                "status": job.status.value,
                "results": job.results,
                "error": job.error,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
    
    def update_max_workers(self, max_workers: int):
        """Update the maximum number of concurrent backtests."""
        with self.lock:
            # Shutdown old executor
            self.executor.shutdown(wait=False)
            # Create new executor with updated max_workers
            self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="backtest")


# Global worker instance
_backtest_worker: Optional[BacktestWorker] = None
_worker_lock = Lock()


def get_backtest_worker() -> BacktestWorker:
    """Get or create the global backtest worker."""
    global _backtest_worker
    
    with _worker_lock:
        if _backtest_worker is None:
            # Get max_workers from admin settings or default to 3
            from ..db.session import SessionLocal
            from ..db.models import AdminSettings
            
            db = SessionLocal()
            try:
                settings = db.query(AdminSettings).filter(AdminSettings.id == "default").first()
                max_workers = getattr(settings, 'max_concurrent_backtests', 3) if settings else 3
            except:
                max_workers = 3
            finally:
                db.close()
            
            _backtest_worker = BacktestWorker(max_workers=max_workers)
        return _backtest_worker

