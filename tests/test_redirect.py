import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "redirect_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import app.config
    import app.database
    import app.models
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


def test_redirect_returns_302_to_long_url(client):
    created = client.post("/shorten", json={"long_url": "https://example.com/target"})
    short_code = created.json()["short_code"]

    response = client.get(f"/{short_code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].rstrip("/") == "https://example.com/target"


def test_redirect_returns_404_for_unknown_code(client):
    response = client.get("/does-not-exist", follow_redirects=False)

    assert response.status_code == 404


def test_health_and_shorten_routes_are_not_shadowed_by_catch_all(client):
    health = client.get("/health", follow_redirects=False)
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
