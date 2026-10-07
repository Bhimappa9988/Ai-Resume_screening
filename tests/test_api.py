import pytest
from fastapi.testclient import TestClient
from src.api import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_get_results_endpoint(client):
    response = client.get("/results")
    assert response.status_code == 200
    data = response.json()
    assert "batch_summary" in data or "candidates" in data
