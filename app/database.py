from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    url=settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo = True
)
SessionLocal  = sessionmaker(
    bind= engine,
    autoflush=False,
    autocommit = False,
    expire_on_commit=False
)

@contextmanager
def get_db_session() ->Generator[Session,None, None]:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()