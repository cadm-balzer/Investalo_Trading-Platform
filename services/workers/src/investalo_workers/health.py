"""Health signal contains no identities or credentials and performs no DB login."""
import os
from pathlib import Path
import time


def location() -> Path:
    return Path(os.getenv("WORKER_HEALTH_FILE", "/tmp/worker-health"))


def mark_healthy():
    location().write_text("ok\n")


def main():
    try:
        age = time.time() - location().stat().st_mtime
    except OSError:
        raise SystemExit(1) from None
    if not -5 <= age <= 120:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
