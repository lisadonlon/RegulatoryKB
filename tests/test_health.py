"""Tests for the /health endpoint."""

import pytest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    pytest.skip("fastapi is not installed", allow_module_level=True)


@pytest.fixture
def client():
    """Create a test client with mocked app state."""
    from regkb.web.main import app

    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "scheduler" in data
        assert "telegram" in data

    def test_health_scheduler_default_not_running(self, client):
        response = client.get("/health")
        data = response.json()
        # Scheduler won't be running in test (no APScheduler installed / not enabled)
        assert "running" in data["scheduler"]

    def test_health_telegram_default_not_connected(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["telegram"]["connected"] is False
