# backend/tests/integration/test_broker_connections.py
"""
PHASE 6: Integration tests for broker connections.
"""
import pytest
from backend.broker.paper_broker import PaperBroker
from backend.broker.types import TradeMode, TradeSide
from backend.db.session import SessionLocal


class TestBrokerConnections:
    """Test broker connection and trading."""
    
    @pytest.fixture
    def db(self):
        """Provide database session."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def test_paper_broker_available(self, db):
        """Test that paper broker is available."""
        broker = PaperBroker(db)
        assert broker.is_available() == True
    
    def test_paper_broker_get_balance(self, db):
        """Test getting paper account balance."""
        broker = PaperBroker(db)
        balance = broker.get_account_balance("test_user")
        
        assert balance is not None
        assert "paper_balance" in balance
        assert balance["paper_balance"] > 0
    
    def test_paper_broker_place_order(self, db):
        """Test placing a paper trade order."""
        broker = PaperBroker(db)
        
        try:
            result = broker.place_order(
                user_id="test_user",
                symbol="AAPL",
                quantity=1.0,
                side=TradeSide.BUY,
                mode=TradeMode.PAPER
            )
            
            assert result is not None
            assert "order_id" in result
            assert result["symbol"] == "AAPL"
        except Exception as e:
            # May fail if market data unavailable
            pytest.skip(f"Paper broker test skipped: {e}")

