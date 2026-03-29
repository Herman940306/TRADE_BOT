"""
conftest.py — Unit Test Session Configuration

Pre-patches database and external service dependencies that would otherwise
require a live PostgreSQL connection, psycopg2 binary, or prometheus_client
to be installed in order to import app modules.

This conftest is loaded automatically by pytest before any test module
in tests/unit/ is collected, ensuring module-level side effects in
app/database/session.py and app/observability/metrics.py do not break
offline unit tests.
"""

import sys
from unittest.mock import MagicMock


def _stub(name: str) -> MagicMock:
    """Register a MagicMock stub under sys.modules[name] and return it."""
    m = MagicMock()
    sys.modules[name] = m
    return m


# ---------------------------------------------------------------------------
# C-extension / optional service stubs
# (must be registered BEFORE any app module is first imported)
# ---------------------------------------------------------------------------
for _ext in (
    "psycopg2",
    "psycopg2.extensions",
    "psycopg2.extras",
    "asyncpg",
    "prometheus_client",
    "aioredis",
    "redis",
):
    if _ext not in sys.modules:
        _stub(_ext)

# ---------------------------------------------------------------------------
# Database session stub
# Prevents app/database/session.py from calling create_engine() at import
# ---------------------------------------------------------------------------
_db_stub = _stub("app.database.session")
_db_stub.SessionLocal = MagicMock()
_db_stub.engine = MagicMock()
_db_stub.get_db = MagicMock()

_db_pkg_stub = _stub("app.database")
_db_pkg_stub.SessionLocal = MagicMock()
_db_pkg_stub.engine = MagicMock()
_db_pkg_stub.get_db = MagicMock()

# ---------------------------------------------------------------------------
# Observability stub (prometheus counters)
# app/observability/__init__.py imports from prometheus_client at module scope
# ---------------------------------------------------------------------------
_obs_stub = _stub("app.observability")
_obs_stub.metrics = MagicMock()
_stub("app.observability.metrics")
_stub("app.observability.rgi_metrics")
