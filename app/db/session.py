"""
Database session factory and per-request ACL setup.

The key invariant: every query that touches chunks or employee_records
runs inside a transaction that has already stamped the app.* GUC
variables via SET LOCAL (or set_config .. is_local=true).  Combined with
the RLS policies in 003_rls_policies.sql this gives us *two* independent
enforcement layers.
"""

from contextlib import contextmanager
from typing import Generator

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth.dependencies import get_current_user
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=5)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=Session,
)


def _set_app_locals(db: Session, user_id: str, user_role: str, tenant_id: str) -> None:
    """Stamp the per-transaction session variables used by ACL predicates.

    Uses set_config(..., is_local=true) which is equivalent to SET LOCAL:
    the value lives only for the current transaction and is automatically
    discarded on commit / rollback.
    """
    db.execute(
        text("SELECT set_config('app.tenant_id', :v, true)"),
        {"v": str(tenant_id)},
    )
    db.execute(
        text("SELECT set_config('app.user_id', :v, true)"),
        {"v": str(user_id)},
    )
    db.execute(
        text("SELECT set_config('app.user_role', :v, true)"),
        {"v": str(user_role)},
    )


@contextmanager
def get_db_session(user_claims: dict) -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLAlchemy Session inside a transaction
    that has the app.* variables set from the JWT claims.

    Usage:
        with get_db_session(user_claims) as db:
            db.execute(text(...))
    """
    db = SessionLocal()
    try:
        with db.begin():
            _set_app_locals(
                db,
                str(user_claims["user_id"]),
                str(user_claims["role"]),
                str(user_claims["tenant_id"]),
            )
            yield db
    finally:
        db.close()


def get_db(user_claims: dict = Depends(get_current_user)):
    """FastAPI dependency: yields a DB session with app.* ACL vars set."""
    with get_db_session(user_claims) as db:
        yield db
