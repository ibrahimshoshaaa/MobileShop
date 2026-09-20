"""Local persistence for the desktop POS.

Reuses backend/functions/persistence/sqlite_repository.SQLiteRepository as-is
(the durable local store already implemented and tested for the offline-first
design) instead of building a second, separate local database layer. Each
desktop install gets its own SQLite file under apps/desktop/data/ — there is
no device-to-device sync here, only the same command outbox pattern the
mobile app and the backend design already share, ready for a future central
sync protocol.
"""
import sys
from pathlib import Path

# Make `backend` / `shared` importable regardless of how this script is
# launched (direct script run, -m, or import from another module), the same
# way tests/conftest.py does it for the test suite.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.functions.persistence.sqlite_repository import SQLiteRepository  # noqa: E402

DEFAULT_TENANT_ID = "LOCAL_TENANT"
DEFAULT_BRANCH_ID = "LOCAL_BRANCH"

_DB_PATH = Path(__file__).resolve().parent / "data" / "desktop_erp.db"

_store: SQLiteRepository | None = None


def get_store() -> SQLiteRepository:
    global _store
    if _store is None:
        _store = SQLiteRepository(_DB_PATH)
    return _store
