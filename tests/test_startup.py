import importlib

from fastapi.testclient import TestClient


def _reload_app_with_fresh_db_url(db_path):
    import app.config
    import app.database
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.main)
    return app.main


def test_create_all_does_not_run_on_import(tmp_path, monkeypatch):
    db_path = tmp_path / "import_only.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    _reload_app_with_fresh_db_url(db_path)

    assert not db_path.exists()


def test_create_all_runs_on_startup(tmp_path, monkeypatch):
    db_path = tmp_path / "startup.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    main_module = _reload_app_with_fresh_db_url(db_path)

    with TestClient(main_module.app):
        assert db_path.exists()
