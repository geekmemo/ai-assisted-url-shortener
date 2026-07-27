from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session


def _create_link(test_client, long_url):
    response = test_client.post("/shorten", json={"long_url": long_url})
    return response.json()["short_code"]


def test_click_count_increments_on_redirect(client):
    test_client, main_module = client
    short_code = _create_link(test_client, "https://example.com/click-test")

    test_client.get(f"/{short_code}", follow_redirects=False)
    test_client.get(f"/{short_code}", follow_redirects=False)

    with Session(bind=main_module.engine) as session:
        link = session.query(main_module.Link).filter_by(short_code=short_code).one()
        assert link.click_count == 2


def test_redirect_creates_timestamped_click_log_entry(client):
    test_client, main_module = client
    short_code = _create_link(test_client, "https://example.com/click-log")

    test_client.get(f"/{short_code}", follow_redirects=False)

    with Session(bind=main_module.engine) as session:
        link = session.query(main_module.Link).filter_by(short_code=short_code).one()
        clicks = session.query(main_module.Click).filter_by(link_id=link.id).all()
        assert len(clicks) == 1
        assert clicks[0].clicked_at is not None


def test_click_count_increments_atomically_under_concurrency(client):
    test_client, main_module = client
    short_code = _create_link(test_client, "https://example.com/concurrent")

    request_count = 25

    def hit(_):
        test_client.get(f"/{short_code}", follow_redirects=False)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(hit, range(request_count)))

    with Session(bind=main_module.engine) as session:
        link = session.query(main_module.Link).filter_by(short_code=short_code).one()
        clicks = session.query(main_module.Click).filter_by(link_id=link.id).all()
        assert link.click_count == request_count
        assert len(clicks) == request_count
