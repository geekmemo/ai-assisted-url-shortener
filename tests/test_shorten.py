def test_shorten_creates_link_and_returns_201(client):
    test_client, _ = client

    response = test_client.post("/shorten", json={"long_url": "https://example.com/some/path"})

    assert response.status_code == 201
    body = response.json()
    assert len(body["short_code"]) == 7
    assert body["long_url"].rstrip("/") == "https://example.com/some/path"


def test_shorten_rejects_invalid_url(client):
    test_client, _ = client

    response = test_client.post("/shorten", json={"long_url": "not-a-url"})

    assert response.status_code == 422


def test_shorten_rejects_url_beyond_pydantics_own_2083_cap(client):
    # Pydantic's HttpUrl itself rejects anything over 2083 chars before our
    # own validator ever runs. This proves that upstream cap still applies.
    test_client, _ = client
    oversized_path = "a" * 3000

    response = test_client.post("/shorten", json={"long_url": f"https://example.com/{oversized_path}"})

    assert response.status_code == 422


def test_shorten_rejects_url_over_our_configured_max_length(client):
    # Between our 2048-char config limit and Pydantic's own 2083-char cap:
    # only our field_validator in app/schemas.py rejects this, so this is
    # the test that actually exercises that code path (the 3000-char case
    # above never reaches it — Pydantic's own limit fires first).
    test_client, _ = client
    url_over_our_limit = "https://example.com/" + ("a" * 2050)
    assert len(url_over_our_limit) > 2048
    assert len(url_over_our_limit) < 2083

    response = test_client.post("/shorten", json={"long_url": url_over_our_limit})

    assert response.status_code == 422
    assert "exceeds maximum length" in response.text


def test_shorten_retries_on_collision(client, monkeypatch):
    test_client, main_module = client
    codes = iter(["AAAAAAA", "AAAAAAA", "BBBBBBB"])
    monkeypatch.setattr(main_module, "generate_short_code", lambda length: next(codes))

    first = test_client.post("/shorten", json={"long_url": "https://example.com/a"})
    assert first.status_code == 201
    assert first.json()["short_code"] == "AAAAAAA"

    second = test_client.post("/shorten", json={"long_url": "https://example.com/b"})
    assert second.status_code == 201
    assert second.json()["short_code"] == "BBBBBBB"


def test_shorten_exhausts_retries_returns_503(client, monkeypatch):
    test_client, main_module = client
    monkeypatch.setattr(main_module, "generate_short_code", lambda length: "SAME001")

    first = test_client.post("/shorten", json={"long_url": "https://example.com/a"})
    assert first.status_code == 201

    second = test_client.post("/shorten", json={"long_url": "https://example.com/b"})
    assert second.status_code == 503
