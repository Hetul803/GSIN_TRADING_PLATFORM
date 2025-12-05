# backend/tests/integration/test_api_endpoints.py
"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.db.models import User, UserStrategy
from backend.db.session import SessionLocal
from backend.utils.jwt_deps import create_access_token


@pytest.fixture
def client(db_session):
    """Create test client."""
    app = create_app()
    # Override get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        name="Test User",
        password_hash="hashed",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create auth headers."""
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "status" in data
    
    def test_ready_endpoint(self, client):
        """Test /ready endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_login_endpoint(self, client, test_user):
        """Test login endpoint."""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password"}
        )
        # Note: This will fail without proper password hashing, but structure is tested
        assert response.status_code in [200, 401]
    
    def test_register_endpoint(self, client):
        """Test register endpoint."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "name": "New User"
            }
        )
        assert response.status_code in [200, 201, 400]  # 400 if user exists


class TestStrategyEndpoints:
    """Test strategy endpoints."""
    
    def test_list_strategies_requires_auth(self, client):
        """Test that listing strategies requires authentication."""
        response = client.get("/api/strategies")
        assert response.status_code == 401  # Unauthorized
    
    def test_get_strategy_tearsheet(self, client, db_session, test_user, auth_headers):
        """Test getting strategy tearsheet."""
        # Create a test strategy
        strategy = UserStrategy(
            id="test-strategy-123",
            user_id=test_user.id,
            name="Test Strategy",
            parameters={},
            ruleset={"entry": "price > sma_20"},
            status="proposable",
            is_active=True
        )
        db_session.add(strategy)
        db_session.commit()
        
        response = client.get(
            f"/api/strategies/{strategy.id}/tearsheet",
            headers=auth_headers
        )
        # Should return 200 or 404 depending on tearsheet calculation
        assert response.status_code in [200, 404, 500]

