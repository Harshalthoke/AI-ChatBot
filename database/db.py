"""Database connection and lifecycle management for SQLite."""

import sqlite3
import os
import logging
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from config.settings import settings

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Returns absolute path to the SQLite database file and ensures parent dir exists."""
    db_path = getattr(settings, "db_path", None) or getattr(settings, "sqlite_db_path", None)
    if db_path is None:
        db_path = settings.base_dir / "data" / "journal_finder.db"
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = settings.base_dir / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_database() -> None:
    """Initializes tables from schema.sql if not already present."""
    db_path = get_db_path()
    schema_file = Path(__file__).parent / "schema.sql"

    if not schema_file.exists():
        logger.error(f"Schema file not found at {schema_file}")
        return

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        with open(schema_file, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    logger.info(f"Database initialized successfully at {db_path}")


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connections."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction rolled back due to error: {e}")
        raise
    finally:
        conn.close()
