from sqlmodel import SQLModel, create_engine, Session
from os import environ

DATABASE_URL = environ.get("DATABASE_URL", "sqlite:///./gsp.db")

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
