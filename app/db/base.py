"""
Shared SQLAlchemy declarative base.

All ORM models inherit from `Base`. Kept in its own module (separate from
session.py) so Alembic's env.py can import metadata without pulling in the
async engine / session machinery.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
