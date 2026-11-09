"""Fixed normal-development identity; explicit single cycle, no public listener."""
import argparse
import os

from .paper_main import configured_worker


def require_preview():
    expected = {
        "PGHOST": "postgres", "PGPORT": "5432", "PGDATABASE": "investalo",
        "PGUSER": "investalo_paper_preview", "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": "/run/secrets/local_ca_cert",
        "PGPASSWORD_FILE": "/run/secrets/paper_preview_password",
    }
    if (os.getenv("PAPER_WORKER_ENABLED") != "1" or os.getenv("PAPER_PUBLIC_PREVIEW_MODE") != "1"
            or any(os.getenv(key) != value for key, value in expected.items())
            or any(key.startswith("PG") and key not in expected for key in os.environ)):
        raise ValueError()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    try:
        require_preview()
        result = configured_worker().run_once()
        print(f"Paper preview committed revision={result.revision}"
              f" updates={result.updates} fills={result.fills}")
    except Exception:
        # A new explicit process must reconcile via readback; never retry a write.
        raise SystemExit("Paper preview cycle unconfirmed; readback required;"
                         " sensitive output suppressed") from None


if __name__ == "__main__":
    main()
