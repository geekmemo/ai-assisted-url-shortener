import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient bound to a fresh app instance with an isolated SQLite file
    and a reset rate limiter. Every module that could hold cross-test state
    (config, database, models, rate_limiter, webhook, main) is reloaded
    together so a module added later can't be silently left stale, the way
    app.rate_limiter was before this fixture existed.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import app.config
    import app.database
    import app.models
    import app.rate_limiter
    import app.webhook
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)
    importlib.reload(app.rate_limiter)
    importlib.reload(app.webhook)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client, app.main
