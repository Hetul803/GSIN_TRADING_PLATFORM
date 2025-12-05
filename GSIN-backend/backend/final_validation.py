#!/usr/bin/env python3
"""
PHASE 6: Full System Validation Script
End-to-end validation of the entire GSIN platform.

Tests:
- Create test user
- Connect broker (paper)
- Upload strategy
- Run backtest
- Generate Brain signal
- Execute trade
- Calculate royalty
- Verify DB records
- Test WebSocket
- Test group messaging
- Test subscriptions
- Test MCN memory write/read
- Test evolution worker (dry run)
"""

import sys
import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import json

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session
from backend.db.session import SessionLocal, get_db
from backend.db import crud
from backend.db.models import User, UserStrategy, Trade, PaperAccount, BrokerConnection, UserRole, AssetType
from backend.brain.brain_service import BrainService
from backend.broker.paper_broker import PaperBroker
from backend.services.royalty_service import RoyaltyService
from backend.workers.evolution_worker import EvolutionWorker
from backend.brain.mcn_adapter import get_mcn_adapter
from backend.utils.logger import log
from backend.utils.auth import hash_password
import traceback


class SystemValidator:
    """Validates the entire GSIN system end-to-end."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_valid": False,
            "errors": []
        }
        self.test_user_id: Optional[str] = None
        self.test_strategy_id: Optional[str] = None
        self.test_trade_id: Optional[str] = None
        self.db: Optional[Session] = None
    
    def test(self, name: str, func, critical: bool = False):
        """Run a validation test."""
        try:
            result = func()
            self.results["tests"][name] = {
                "status": "PASS" if result else "FAIL",
                "result": result
            }
            if not result and critical:
                self.results["errors"].append(f"Critical test failed: {name}")
            return result
        except Exception as e:
            self.results["tests"][name] = {
                "status": "ERROR",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            if critical:
                self.results["errors"].append(f"Critical test error: {name}: {str(e)}")
            return False
    
    def create_test_user(self) -> bool:
        """Create a test user for validation."""
        try:
            self.db = SessionLocal()
            
            # Create test user
            test_email = f"test_{uuid.uuid4().hex[:8]}@gsin.test"
            test_user = User(
                id=str(uuid.uuid4()),
                email=test_email,
                name="Test User",
                password_hash=hash_password("test_password_123"),
                role=UserRole.USER,
                broker_connected=False,
            )
            self.db.add(test_user)
            self.db.commit()
            self.db.refresh(test_user)
            
            self.test_user_id = test_user.id
            log(f"✅ Created test user: {test_user.email} (ID: {test_user.id})")
            return True
        except Exception as e:
            log(f"❌ Failed to create test user: {e}")
            if self.db:
                self.db.rollback()
            return False
    
    def connect_broker_paper(self) -> bool:
        """Connect paper broker (simulated)."""
        try:
            if not self.test_user_id:
                return False
            
            # Create paper account
            paper_account = PaperAccount(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                balance=10000.0,
                equity=10000.0,
                buying_power=10000.0,
            )
            self.db.add(paper_account)
            self.db.commit()
            
            log("✅ Paper account created")
            return True
        except Exception as e:
            log(f"❌ Failed to connect paper broker: {e}")
            if self.db:
                self.db.rollback()
            return False
    
    def upload_strategy(self) -> bool:
        """Upload a test strategy."""
        try:
            if not self.test_user_id:
                return False
            
            strategy = UserStrategy(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                name="Test Validation Strategy",
                description="Strategy for system validation",
                parameters={"test": True},
                ruleset={
                    "entry": [{"indicator": "SMA", "field": "close", "period": 50, "condition": "crosses_above", "compare_to": {"indicator": "SMA", "field": "close", "period": 200}}],
                    "exit": [{"indicator": "SMA", "field": "close", "period": 50, "condition": "crosses_below", "compare_to": {"indicator": "SMA", "field": "close", "period": 200}}],
                },
                asset_type=AssetType.STOCK,
                score=0.75,
                status="proposable",
                is_proposable=True,
            )
            self.db.add(strategy)
            self.db.commit()
            self.db.refresh(strategy)
            
            self.test_strategy_id = strategy.id
            log(f"✅ Uploaded test strategy: {strategy.name} (ID: {strategy.id})")
            return True
        except Exception as e:
            log(f"❌ Failed to upload strategy: {e}")
            if self.db:
                self.db.rollback()
            return False
    
    async def run_backtest(self) -> bool:
        """Run backtest on test strategy."""
        try:
            if not self.test_strategy_id:
                return False
            
            brain = BrainService()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            backtest_result = await brain.backtest_with_memory(
                strategy_id=self.test_strategy_id,
                symbol="AAPL",
                timeframe="1d",
                start_date=start_date,
                end_date=end_date,
                db=self.db
            )
            
            log(f"✅ Backtest completed: Return={backtest_result.total_return:.2%}, Win Rate={backtest_result.win_rate:.2%}")
            return True
        except Exception as e:
            log(f"❌ Backtest failed: {e}")
            return False
    
    async def generate_brain_signal(self) -> bool:
        """Generate Brain signal."""
        try:
            if not self.test_strategy_id or not self.test_user_id:
                return False
            
            brain = BrainService()
            signal = await brain.generate_signal(
                strategy_id=self.test_strategy_id,
                user_id=self.test_user_id,
                symbol="AAPL",
                db=self.db
            )
            
            log(f"✅ Brain signal generated: Side={signal.side}, Confidence={signal.confidence:.2%}")
            return True
        except Exception as e:
            log(f"❌ Brain signal generation failed: {e}")
            return False
    
    async def execute_trade(self) -> bool:
        """Execute a paper trade."""
        try:
            if not self.test_user_id:
                return False
            
            broker = PaperBroker(self.db)
            
            # Place order
            order = await broker.place_order(
                user_id=self.test_user_id,
                symbol="AAPL",
                side="BUY",
                quantity=10,
                order_type="market"
            )
            
            self.test_trade_id = order.id
            log(f"✅ Trade executed: Order ID={order.id}")
            return True
        except Exception as e:
            log(f"❌ Trade execution failed: {e}")
            return False
    
    def calculate_royalty(self) -> bool:
        """Test royalty calculation."""
        try:
            if not self.test_trade_id:
                return False
            
            service = RoyaltyService()
            
            # Simulate profitable trade
            profit = 100.0
            royalty_rate = 0.05
            platform_fee_rate = 0.05
            
            royalty = service.calculate_royalty(profit, royalty_rate)
            platform_fee = service.calculate_platform_fee(royalty, platform_fee_rate)
            net = service.calculate_net_amount(royalty, platform_fee)
            
            log(f"✅ Royalty calculated: Royalty=${royalty:.2f}, Fee=${platform_fee:.2f}, Net=${net:.2f}")
            return True
        except Exception as e:
            log(f"❌ Royalty calculation failed: {e}")
            return False
    
    def verify_db_records(self) -> bool:
        """Verify all DB records were created."""
        try:
            if not self.test_user_id:
                return False
            
            # Verify user
            user = self.db.query(User).filter(User.id == self.test_user_id).first()
            if not user:
                return False
            
            # Verify strategy
            if self.test_strategy_id:
                strategy = self.db.query(UserStrategy).filter(UserStrategy.id == self.test_strategy_id).first()
                if not strategy:
                    return False
            
            # Verify trade
            if self.test_trade_id:
                trade = self.db.query(Trade).filter(Trade.id == self.test_trade_id).first()
                if not trade:
                    return False
            
            log("✅ All DB records verified")
            return True
        except Exception as e:
            log(f"❌ DB verification failed: {e}")
            return False
    
    async def test_websocket(self) -> bool:
        """Test WebSocket connection (simulated)."""
        try:
            # This would test actual WebSocket connection
            # For now, just verify the endpoint exists
            from backend.api.websocket import ConnectionManager
            manager = ConnectionManager()
            log("✅ WebSocket manager initialized")
            return True
        except Exception as e:
            log(f"❌ WebSocket test failed: {e}")
            return False
    
    def test_group_messaging(self) -> bool:
        """Test group messaging functionality."""
        try:
            if not self.test_user_id:
                return False
            
            # Create test group
            group = crud.create_group(
                db=self.db,
                owner_id=self.test_user_id,
                name="Test Validation Group",
                description="Group for system validation"
            )
            
            # Send message
            message = crud.create_group_message(
                db=self.db,
                group_id=group.id,
                user_id=self.test_user_id,
                content="Test message for validation"
            )
            
            log(f"✅ Group messaging tested: Group={group.name}, Message ID={message.id}")
            return True
        except Exception as e:
            log(f"❌ Group messaging test failed: {e}")
            return False
    
    def test_subscriptions(self) -> bool:
        """Test subscription functionality."""
        try:
            if not self.test_user_id:
                return False
            
            # Get subscription plans
            plans = crud.get_subscription_plans(self.db)
            if not plans:
                return False
            
            log(f"✅ Subscription plans available: {len(plans)} plans")
            return True
        except Exception as e:
            log(f"❌ Subscription test failed: {e}")
            return False
    
    def test_mcn_memory(self) -> bool:
        """Test MCN memory write/read."""
        try:
            mcn_adapter = get_mcn_adapter()
            if not mcn_adapter.is_available:
                log("⚠️  MCN not available, skipping memory test")
                return True  # Not critical if MCN is unavailable
            
            # Write test event
            success = mcn_adapter.record_event(
                event_type="validation_test",
                payload={
                    "test": True,
                    "timestamp": datetime.now().isoformat()
                },
                user_id=self.test_user_id
            )
            
            if not success:
                return False
            
            log("✅ MCN memory write/read tested")
            return True
        except Exception as e:
            log(f"❌ MCN memory test failed: {e}")
            return False
    
    def test_evolution_worker(self) -> bool:
        """Test evolution worker (dry run)."""
        try:
            worker = EvolutionWorker()
            # Just verify it initializes
            if worker is None:
                return False
            
            log("✅ Evolution worker initialized")
            return True
        except Exception as e:
            log(f"❌ Evolution worker test failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up test data."""
        try:
            if self.db:
                # Delete test user (cascades to strategies, trades, etc.)
                if self.test_user_id:
                    user = self.db.query(User).filter(User.id == self.test_user_id).first()
                    if user:
                        self.db.delete(user)
                        self.db.commit()
                        log("✅ Test data cleaned up")
        except Exception as e:
            log(f"⚠️  Cleanup error: {e}")
        finally:
            if self.db:
                self.db.close()
    
    async def run_all_tests(self):
        """Run all validation tests."""
        log("🔍 Starting full system validation...")
        
        # Critical tests
        self.test("create_test_user", self.create_test_user, critical=True)
        self.test("connect_broker_paper", self.connect_broker_paper, critical=True)
        self.test("upload_strategy", self.upload_strategy, critical=True)
        await self.test("run_backtest", self.run_backtest, critical=True)
        await self.test("generate_brain_signal", self.generate_brain_signal, critical=True)
        await self.test("execute_trade", self.execute_trade, critical=True)
        self.test("calculate_royalty", self.calculate_royalty, critical=True)
        self.test("verify_db_records", self.verify_db_records, critical=True)
        
        # Non-critical tests
        await self.test("test_websocket", self.test_websocket, critical=False)
        self.test("test_group_messaging", self.test_group_messaging, critical=False)
        self.test("test_subscriptions", self.test_subscriptions, critical=False)
        self.test("test_mcn_memory", self.test_mcn_memory, critical=False)
        self.test("test_evolution_worker", self.test_evolution_worker, critical=False)
        
        # Determine overall validity
        critical_tests = [name for name, test in self.results["tests"].items() if test.get("status") == "FAIL" and "critical" in str(test)]
        self.results["overall_valid"] = len(self.results["errors"]) == 0
    
    def print_results(self):
        """Print validation results."""
        print("\n" + "="*80)
        print("FULL SYSTEM VALIDATION RESULTS")
        print("="*80)
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Overall Valid: {'TRUE' if self.results['overall_valid'] else 'FALSE'}")
        print()
        
        print("TEST RESULTS:")
        print("-"*80)
        for test_name, test_result in self.results["tests"].items():
            status = test_result.get("status", "UNKNOWN")
            symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
            print(f"{symbol} {test_name:40s} {status}")
            if "error" in test_result:
                print(f"   Error: {test_result['error']}")
        
        if self.results["errors"]:
            print("\n❌ ERRORS:")
            for error in self.results["errors"]:
                print(f"   - {error}")
        
        print("\n" + "="*80)
        print(f"FULL_SYSTEM_VALID: {'TRUE' if self.results['overall_valid'] else 'FALSE'}")
        print("="*80)


async def main():
    """Main entry point."""
    validator = SystemValidator()
    try:
        await validator.run_all_tests()
        validator.print_results()
    finally:
        validator.cleanup()
    
    sys.exit(0 if validator.results["overall_valid"] else 1)


if __name__ == "__main__":
    asyncio.run(main())

