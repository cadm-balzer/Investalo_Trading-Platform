"""Offline polling process. Broker I/O and BFF identity are deliberately absent."""
import argparse
import signal
from threading import Event

from .research import run_once
from .settings import WorkerSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        settings = WorkerSettings.from_environment()
        while not stopped.is_set():
            try:
                claimed = run_once(settings)
            except Exception:
                if args.once:
                    raise SystemExit("Research cycle unavailable; no diagnostic secrets emitted") from None
                stopped.wait(5)
                continue
            if args.once:
                print("Research cycle processed a frozen job." if claimed else "No eligible research job.")
                break
            if not claimed:
                stopped.wait(2)
    except (ValueError, OSError):
        raise SystemExit("Research worker configuration unavailable") from None


if __name__ == "__main__":
    main()
