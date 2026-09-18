"""
Database configuration for SQLite3 connections.
This module provides database path constants for sync sqlite3 operations.
"""

import os
import shutil
from pathlib import Path

# Database files live beneath the persistent application data directory.
DATA_DIRECTORY = Path("data")
DATABASE_NAME = str(DATA_DIRECTORY / "botdata.db")
LEGACY_DATABASE_NAME = "botdata.db"


def ensure_database_directory() -> None:
    """Create the data directory and preserve an existing legacy database."""
    DATA_DIRECTORY.mkdir(exist_ok=True)
    database_path = Path(DATABASE_NAME)
    legacy_path = Path(LEGACY_DATABASE_NAME)
    if legacy_path.exists() and not database_path.exists():
        shutil.copy2(legacy_path, database_path)


def get_database_path() -> str:
    """Get the absolute path to the database file."""
    ensure_database_directory()
    return os.path.abspath(DATABASE_NAME)
