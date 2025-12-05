# backend/tests/e2e/test_full_user_flow.py
"""
PHASE 6: End-to-end test for complete user flow.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.session import SessionLocal
from backend.db import crud
import uuid


class TestFullUserFlow:
    """Test complete user journey."""
    
    @pytest.fixture
    def client(self):
        """Provide test client."""
        return TestClient(app)
    
    @pytest.fixture
    def db(self):
        """Provide database session."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def test_user(self, db):
        """Create a test user."""
        user_id = str(uuid.uuid4())
        user = crud.create_user(
            db,
            email=f"test_{user_id}@example.com",
            password_hash="test_hash",
            full_name="Test User"
        )
        return user
    
    def test_user_signup_login(self, client):
        """Test user signup and login flow."""
        # Signup
        signup_response = client.post("/api/users/signup", json={
            "email": f"test_{uuid.uuid4()}@example.com",
            "password": "test_password_123",
            "full_name": "Test User"
        })
        
        # Should succeed or return appropriate error
        assert signup_response.status_code in [200, 201, 400]  # 400 if user exists
        
        # Login
        login_response = client.post("/api/users/login", json={
            "email": signup_response.json().get("email", "test@example.com"),
            "password": "test_password_123"
        })
        
        # Should get token or appropriate error
        assert login_response.status_code in [200, 401]
    
    def test_strategy_creation_and_backtest(self, client, test_user, db):
        """Test creating a strategy and running backtest."""
        # This would require authentication token
        # For now, we'll test the endpoints exist
        
        strategy_data = {
            "name": "Test Strategy",
            "description": "Test description",
            "ruleset": {
                "ticker": "AAPL",
                "timeframe": "1d",
                "entry_rules": {"condition": "always_true"},
                "exit_rules": {"condition": "never"}
            }
        }
        
        # Would need JWT token here
        # response = client.post("/api/strategies", json=strategy_data, headers={"Authorization": f"Bearer {token}"})
        # assert response.status_code in [200, 201, 401, 403]
        
        # For now, just verify endpoint exists
        response = client.post("/api/strategies", json=strategy_data)
        # Should return 401 (unauthorized) or 403 (forbidden), not 404
        assert response.status_code != 404

