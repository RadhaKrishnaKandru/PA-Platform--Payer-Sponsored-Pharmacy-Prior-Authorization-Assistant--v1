"""Tests for the initial API health route."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    """The liveness endpoint responds successfully without database services."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_vite_origin_can_access_api() -> None:
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_vite_origin_can_preflight_json_post() -> None:
    response = client.options(
        "/api/cases",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_other_origins_are_not_allowed() -> None:
    response = client.get(
        "/api/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
