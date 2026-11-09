"""Bound PostgreSQL checkpoint/journal client; never automatically retry writes."""
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import psycopg
from psycopg.pq import TransactionStatus

from investalo_trading import PaperCheckpoint, PaperRunner, PaperUpdate


class PaperStorageRejected(ValueError):
    pass


class PaperConflict(PaperStorageRejected):
    pass


class PaperCommitUnknown(RuntimeError):
    """Do not retry. Read persisted state on a fresh connection to reconcile."""


def checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class PaperStore:
    runner: PaperRunner
    connect: Callable
    expected_role: str

    def _transaction(self, action):
        db = None
        committing = False
        try:
            db = self.connect()
            if db.autocommit or db.info.transaction_status != TransactionStatus.IDLE:
                raise PaperStorageRejected("Fresh transactional connection required")
            row = db.execute(
                "SELECT current_user AS current,session_user AS session,"
                "rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                "FROM pg_catalog.pg_roles WHERE rolname=session_user",
            ).fetchone()
            if (not row or row["current"] != self.expected_role
                    or row["session"] != self.expected_role
                    or any(row[key] for key in ("rolsuper", "rolcreatedb", "rolcreaterole",
                                               "rolreplication", "rolbypassrls"))):
                raise PaperStorageRejected("Paper identity rejected")
            result = action(db)
            committing = True
            db.commit()
            return result
        except psycopg.errors.SerializationFailure:
            raise PaperConflict("Paper revision conflict") from None
        except psycopg.IntegrityError:
            raise PaperStorageRejected("Paper storage rejected") from None
        except Exception:
            if committing:
                raise PaperCommitUnknown("Paper commit requires readback") from None
            raise PaperStorageRejected("Paper storage rejected") from None
        finally:
            if db is not None:
                # Closing does not repeat a write or overwrite an unknown result.
                try:
                    db.close()
                except Exception:
                    pass

    def _read(self, db) -> PaperCheckpoint | None:
        record = db.execute("SELECT platform.paper_read() AS record").fetchone()["record"]
        if record is None:
            return None
        if (set(record) != {"checkpoint", "checksum", "revision"}
                or checksum(record["checkpoint"]) != record["checksum"]):
            raise PaperStorageRejected("Paper stored checksum rejected")
        checkpoint = self.runner.restore(record["checkpoint"])
        if type(record["revision"]) is not int or checkpoint.revision != record["revision"]:
            raise PaperStorageRejected("Paper stored revision rejected")
        return checkpoint

    def read(self) -> PaperCheckpoint | None:
        return self._transaction(self._read)

    def initialize(self, initial: PaperCheckpoint) -> PaperCheckpoint:
        payload = self.runner.dump(initial)
        if initial.revision != 0:
            raise PaperStorageRejected("Paper initial revision rejected")

        def write(db):
            revision = db.execute("SELECT platform.paper_initialize(%s,%s) AS revision",
                                  (payload, checksum(payload))).fetchone()["revision"]
            if type(revision) is not int or revision != 0:
                raise PaperStorageRejected("Paper initialization rejected")
            return initial
        return self._transaction(write)

    def commit(self, previous: PaperCheckpoint, update: PaperUpdate) -> PaperCheckpoint:
        before = self.runner.dump(previous)
        after = self.runner.dump(update.checkpoint)
        if update.entry is None:
            if previous != update.checkpoint or self.read() != previous:
                raise PaperConflict("Paper duplicate state conflict")
            return previous
        if (update.entry != update.checkpoint.last_entry
                or update.checkpoint.revision != previous.revision + 1):
            raise PaperStorageRejected("Paper update sequence rejected")

        def write(db):
            revision = db.execute(
                "SELECT platform.paper_commit(%s,%s,%s,%s) AS revision",
                (previous.revision, checksum(before), after, checksum(after)),
            ).fetchone()["revision"]
            if type(revision) is not int or revision != update.checkpoint.revision:
                raise PaperStorageRejected("Paper commit result rejected")
            return update.checkpoint
        return self._transaction(write)
