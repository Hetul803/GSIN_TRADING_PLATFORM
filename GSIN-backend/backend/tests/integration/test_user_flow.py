# backend/tests/integration/test_user_flow.py
"""
Integration tests for complete user flows.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import create_app
from backend.db import crud
from backend.db.models import User, UserStrategy, Trade, TradeStatus


class TestUserFlow:
    """Test complete user flows."""
    
    @pytest.fixture
    def client(self, db_session):
        """Create test client."""
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)
    
    @pytest.fixture
    def test_user(self, db_session):
        """Create a test user."""
        user = User(
            id="test-user-123",
            email="test@example.com",
            name="Test User",
            password_hash="hashed_password",
            role="user",
            subscription_tier="user",
        )
        db_session.add(user)
        db_session.commit()
        return user
    
    def test_user_signup_login_flow(self, client, db_session):
        """Test user signup and login flow."""
        # Signup
        signup_response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "name": "New User",
            }
        )
        assert signup_response.status_code == 200 or signup_response.status_code == 201
        
        # Login
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "newuser@example.com",
                "password": "password123",
            }
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()
    
    def test_create_strategy_and_backtest(self, client, test_user, db_session):
        """Test creating a strategy and running a backtest."""
        # Get auth token (simplified - in real test would login first)
        # For now, we'll test the endpoint directly with mocked auth
        
        # This is a simplified test - full implementation would include:
        # 1. Login to get JWT
        # 2. Create strategy with JWT
        # 3. Run backtest with JWT
        # 4. Verify results
        
        # Placeholder for full implementation
        pass
    
    def test_broker_connection_flow(self, client, test_user, db_session):
        """Test broker connection flow."""
        # This would test:
        # 1. Connect broker with manual keys
        # 2. Verify connection
        # 3. Check status
        
        # Placeholder for full implementation
        pass
    
    def test_trade_execution_and_royalty(self, client, test_user, db_session):
        """Test trade execution and royalty calculation."""
        # This would test:
        # 1. Execute a paper trade
        # 2. Close the trade with profit
        # 3. Verify royalty ledger is updated
        
        # Placeholder for full implementation
        pass

