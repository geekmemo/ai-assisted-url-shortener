import importlib

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_path = tmp_path / "models_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import app.config
    import app.database
    import app.models

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.models)

    app.database.Base.metadata.create_all(bind=app.database.engine)

    session = Session(bind=app.database.engine)
    try:
        yield session, app.models.Link
    finally:
        session.close()


def test_link_table_created_and_row_persists(db_session):
    session, Link = db_session

    link = Link(short_code="abc1234", long_url="https://example.com")
    session.add(link)
    session.commit()

    saved = session.query(Link).filter_by(short_code="abc1234").one()
    assert saved.long_url == "https://example.com"
    assert saved.created_at is not None


def test_short_code_unique_constraint_enforced(db_session):
    session, Link = db_session

    session.add(Link(short_code="dup1234", long_url="https://example.com/a"))
    session.commit()

    session.add(Link(short_code="dup1234", long_url="https://example.com/b"))
    with pytest.raises(IntegrityError):
        session.commit()
