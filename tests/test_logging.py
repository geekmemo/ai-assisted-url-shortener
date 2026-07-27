import importlib
import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.logging_config import JsonFormatter


def test_json_formatter_escapes_quotes_and_newlines_correctly():
    # A prior version built the JSON line via string interpolation, which
    # produced invalid JSON whenever the message contained a quote or
    # newline - exactly what exception text (our own failure-path warning
    # logs) commonly contains.
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg='value "weird" caused a\nmulti-line error',
        args=(),
        exc_info=None,
    )

    line = JsonFormatter().format(record)
    parsed = json.loads(line)  # raises if the line isn't valid JSON

    assert parsed["message"] == 'value "weird" caused a\nmulti-line error'
    assert parsed["level"] == "WARNING"


def test_request_completion_is_logged_with_request_id(client, caplog):
    test_client, _ = client

    with caplog.at_level(logging.INFO, logger="app.main"):
        response = test_client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]

    matching = [r for r in caplog.records if "GET /health -> 200" in r.message]
    assert len(matching) == 1
    assert f"request_id={request_id}" in matching[0].message


def test_caller_supplied_request_id_is_honored(client):
    test_client, _ = client

    response = test_client.get("/health", headers={"X-Request-ID": "caller-supplied-id-123"})

    assert response.headers["X-Request-ID"] == "caller-supplied-id-123"


def test_click_recording_failure_is_logged(client, caplog, monkeypatch):
    test_client, _ = client

    created = test_client.post("/shorten", json={"long_url": "https://example.com/logged-failure"})
    short_code = created.json()["short_code"]

    def failing_commit(self):
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(Session, "commit", failing_commit)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        response = test_client.get(f"/{short_code}", follow_redirects=False)

    assert response.status_code == 302

    matching = [r for r in caplog.records if "click recording failed" in r.message]
    assert len(matching) == 1
    assert short_code in matching[0].message


@pytest.fixture
def client_with_webhook(tmp_path, monkeypatch):
    db_path = tmp_path / "logging_webhook_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/hooks/link-created")

    import app.config
    import app.database
    import app.main
    import app.models
    import app.rate_limiter
    import app.webhook

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)
    importlib.reload(app.rate_limiter)
    importlib.reload(app.webhook)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client, app.main, app.webhook


def test_webhook_failure_is_logged(client_with_webhook, caplog, monkeypatch):
    test_client, _, webhook_module = client_with_webhook

    import httpx

    def failing_post(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(webhook_module.httpx, "post", failing_post)

    with caplog.at_level(logging.WARNING, logger="app.webhook"):
        response = test_client.post("/shorten", json={"long_url": "https://example.com/webhook-log-test"})

    assert response.status_code == 201
    short_code = response.json()["short_code"]

    matching = [r for r in caplog.records if "webhook delivery failed" in r.message]
    assert len(matching) == 1
    assert short_code in matching[0].message


@pytest.fixture
def client_with_low_rate_limit(tmp_path, monkeypatch):
    # This reload must happen during fixture setup, not inside the test body:
    # configure_logging() replaces root.handlers wholesale, which would wipe
    # out caplog's own handler if the reload ran after caplog had already
    # attached it. Listing this fixture before `caplog` in each test's
    # parameters (as done below) ensures setup order puts the reload first.
    db_path = tmp_path / "logging_rate_limit_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")

    import app.config
    import app.database
    import app.main
    import app.models
    import app.rate_limiter
    import app.webhook

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)
    importlib.reload(app.rate_limiter)
    importlib.reload(app.webhook)
    importlib.reload(app.main)

    with TestClient(app.main.app) as test_client:
        yield test_client


def test_rate_limited_requests_are_logged(client_with_low_rate_limit, caplog):
    test_client = client_with_low_rate_limit

    with caplog.at_level(logging.INFO, logger="app.main"):
        test_client.get("/some-unknown-code")
        blocked = test_client.get("/some-unknown-code")

    assert blocked.status_code == 429
    matching = [r for r in caplog.records if "-> 429" in r.message]
    assert len(matching) == 1
