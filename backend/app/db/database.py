import contextlib

from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=settings.POSTGRESQL_USERNAME,
    password=settings.POSTGRESQL_PASSWORD,
    host=settings.POSTGRESQL_HOSTNAME,
    port=settings.POSTGRESQL_PORT,
    database=settings.POSTGRESQL_DATABASE,
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()


@contextlib.contextmanager
def get_sess() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
