import pytest
from sqlmodel import create_engine, Session
from models import SQLModel


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    with Session(in_memory_db) as session:
        yield session
