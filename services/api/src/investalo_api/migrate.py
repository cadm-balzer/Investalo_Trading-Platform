"""Apply checked SQL files with the dedicated DDL identity, never API runtime."""
import hashlib
from pathlib import Path

from .database import connect
from .settings import Settings


def main() -> None:
    directory = Path(__file__).resolve().parents[2] / "migrations"
    with connect(Settings.from_environment()) as db:
        role = db.execute("SELECT current_user AS name").fetchone()["name"]
        if role != "investalo_migration":
            raise SystemExit("Migration requires investalo_migration")
        db.execute("SELECT pg_advisory_xact_lock(724809361)")
        db.execute("CREATE SCHEMA IF NOT EXISTS platform")
        db.execute(
            "CREATE TABLE IF NOT EXISTS platform.schema_migrations "
            "(version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        for path in sorted(directory.glob("*.sql")):
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            existing = db.execute(
                "SELECT checksum FROM platform.schema_migrations WHERE version=%s", (path.stem,),
            ).fetchone()
            if existing:
                if existing["checksum"] != digest:
                    raise SystemExit("Applied migration checksum differs")
                continue
            db.execute(content.decode("utf-8"), prepare=False)
            db.execute(
                "INSERT INTO platform.schema_migrations(version,checksum) VALUES (%s,%s)",
                (path.stem, digest),
            )
            print(f"Applied {path.stem}")


if __name__ == "__main__":
    main()
