import importlib

import pytest
from fastapi.testclient import TestClient

from app.rate_limiter import FixedWindowRateLimiter


def test_rate_limiter_allows_up_to_max_then_blocks():
    limiter = FixedWindowRateLimiter(max_requests=3, window_seconds=60)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False


def test_rate_limiter_tracks_keys_independently():
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60)

    assert limiter.allow("1.1.1.1") is True
    assert limiter.allow("1.1.1.1") is False
    assert limiter.allow("2.2.2.2") is True


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "rate_limit_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")

    import app.config
    import app.database
    import app.models
    import app.rate_limiter
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)
    importlib.reload(app.rate_limiter)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


def test_requests_beyond_configured_threshold_get_429(client):
    for _ in range(3):
        response = client.get("/some-unknown-code")
        assert response.status_code == 404

    blocked = client.get("/some-unknown-code")
    assert blocked.status_code == 429


def test_health_endpoint_is_exempt_from_rate_limiting(client):
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200
