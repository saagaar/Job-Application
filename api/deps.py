from __future__ import annotations

from db.database import Database

# Module-level instance set by lifespan at startup.
# All routes use Depends(get_db) — never instantiate Database() directly in routes.
_db: Database | None = None


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialised. Start the app via lifespan.")
    return _db
