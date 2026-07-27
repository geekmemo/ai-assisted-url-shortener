import importlib

import httpx
import pytest
from fastapi.testclient import TestClient


def test_webhook_not_called_when_url_not_configured(client, monkeypatch):
    test_client, _ = client
    import app.webhook as webhook_module

    assert webhook_module.settings.webhook_url is None

    calls = []
    monkeypatch.setattr(webhook_module.httpx, "post", lambda *a, **k: calls.append((a, k)))

    response = test_client.post("/shorten", json={"long_url": "https://example.com/no-webhook"})

    assert response.status_code == 201
    assert calls == []


@pytest.fixture
def client_with_webhook(tmp_path, monkeypatch):
    db_path = tmp_path / "webhook_test.db"
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


def test_webhook_called_with_correct_payload_when_configured(client_with_webhook, monkeypatch):
    test_client, _, webhook_module = client_with_webhook

    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))

        class _Response:
            status_code = 200

        return _Response()

    monkeypatch.setattr(webhook_module.httpx, "post", fake_post)

    response = test_client.post("/shorten", json={"long_url": "https://example.com/with-webhook"})

    assert response.status_code == 201
    short_code = response.json()["short_code"]

    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == "https://example.com/hooks/link-created"
    assert payload == {
        "event": "link_created",
        "short_code": short_code,
        "long_url": "https://example.com/with-webhook",
    }
    assert timeout == 5


def test_shorten_succeeds_even_if_webhook_call_fails(client_with_webhook, monkeypatch):
    test_client, _, webhook_module = client_with_webhook

    def failing_post(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(webhook_module.httpx, "post", failing_post)

    response = test_client.post("/shorten", json={"long_url": "https://example.com/webhook-fails"})

    assert response.status_code == 201
    assert len(response.json()["short_code"]) == 7
