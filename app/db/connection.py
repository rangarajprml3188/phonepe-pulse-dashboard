"""
Shared PostgreSQL connection for the PhonePe Pulse project.

Reads credentials from environment variables (loaded from a .env file
via python-dotenv) instead of hardcoding them, so this file is safe to
commit to git.

Create a `.env` file in your project root (same folder as app.py) with:

    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=phonepe_db
    DB_USER=postgres
    DB_PASSWORD=your_password_here

And add `.env` to your .gitignore.
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env from the project root regardless of where this file is run from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "phonepe_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")


@st.cache_resource(show_spinner=False)
def get_engine():
    """
    Returns a cached SQLAlchemy engine, shared across all Streamlit
    reruns in a session. st.cache_resource ensures we don't open a
    fresh connection pool on every widget interaction.
    """
    if not DB_PASSWORD:
        raise RuntimeError(
            "DB_PASSWORD not set. Create a .env file with your "
            "PostgreSQL credentials (see db/connection.py docstring)."
        )

    url = (
        f"postgresql+psycopg2://"
        f"{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(url, pool_pre_ping=True)

    # Fail fast with a clear error if the DB isn't reachable
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return engine


def run_query(sql, params=None):
    """
    Runs a parametrized SQL query and returns a pandas DataFrame.
    Use SQLAlchemy `:name` style params, e.g.:

        run_query("SELECT * FROM map_transaction WHERE \"Year\" = :year",
                   {"year": 2023})
    """
    import pandas as pd

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})
