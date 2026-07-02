import os
import tempfile

# Point the default engine at a throwaway DB before app modules import.
_tmp = tempfile.mkdtemp(prefix="mki_default_")
os.environ.setdefault("MKI_DATABASE_URL", f"sqlite+pysqlite:///{_tmp}/default.db")

# Force stub mode so tests stay hermetic even if a real key exists in .env.
# (env vars take precedence over the .env file in pydantic-settings.)
os.environ["MKI_OPENROUTER_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.storage import get_session
from app.storage.db import Base
from app.storage import models  # noqa: F401  (register mappers)


@pytest.fixture
def session_factory(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory):
    def _override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
