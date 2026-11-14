"""Private bounded create-only source cohorts, revalidated from native responses."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
import time
from pathlib import Path
from uuid import uuid4

from investalo_trading.futures_paper_source import PaperSourceRef
from investalo_trading.futures_paper_status import _directory, _owned_file
from investalo_trading.futures_replay_journal import _fields
from investalo_trading.snapshot import _decode

from .futures_paper_feed import (
    BitgetFuturesMarketSource, FuturesMarketObservation, MAX_BYTES, fetch_paper_source_json,
)
from .futures_settlement_source import BitgetSettlementSource, SettlementEvidence, fetch_settlement_json
from .snapshot import canonical, decode_json

VERSION = "bitget-classic-futures-paper-archive/1"
MAX_OBSERVATION = 1024 * 1024
MAX_COHORTS = 2000


class PaperArchiveCommitUnknown(RuntimeError):
    """Preserve partial cohort; no journal command or automatic retry."""


def _read(fd, name, limit):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(handle, "rb") as source:
        if _owned_file(source.fileno()).st_size > limit:
            raise ValueError("source archive file exceeds bound")
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("source archive file exceeds bound")
    return raw


def _write(fd, name, value, limit):
    raw = canonical(value).encode()
    if len(raw) > limit:
        raise ValueError("source archive record exceeds bound")
    handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as output:
            _owned_file(output.fileno())
            if output.write(raw) != len(raw):
                raise OSError("short source write")
            output.flush()
            os.fsync(output.fileno())
        if _read(fd, name, limit) != raw:
            raise OSError("source readback mismatch")
    except BaseException:
        raise PaperArchiveCommitUnknown("source acknowledgement unknown; preserve and read back") from None
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class FuturesPaperArchive:
    root: Path
    clock: object = lambda: datetime.now(timezone.utc)
    market_fetch: object = fetch_paper_source_json
    minute_fetch: object = fetch_settlement_json
    sleep: object = time.sleep
    _uncertain: bool = field(default=False, init=False, repr=False, compare=False)

    def market(self, *, start, end, funding_start, guard=lambda: None):
        return self._capture("market", {"start": start, "end": end, "funding_start": funding_start}, guard)

    def minute(self, settled_at, *, guard=lambda: None):
        return self._capture("minute", {"settled_at": settled_at}, guard)

    def _capture(self, kind, parameters, guard):
        if self._uncertain:
            raise PaperArchiveCommitUnknown("source writer stopped; readback before a new instance")
        guard()
        parent = _directory(self.root)
        fd = None
        key, reads = uuid4().hex, []
        try:
            if len(os.listdir(parent)) >= MAX_COHORTS:
                raise ValueError("source cohort capacity exhausted; never delete evidence")
            os.mkdir(key, mode=0o700, dir_fd=parent)
            fd = os.open(key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                os.fsync(parent)
            except OSError:
                raise PaperArchiveCommitUnknown("source directory acknowledgement unknown") from None

            def fetch(url):
                guard()
                payload = (self.market_fetch if kind == "market" else self.minute_fetch)(url)
                guard()
                name = f"response-{len(reads) + 1:02}.json"
                sha = _write(fd, name, payload, MAX_BYTES)
                reads.append({"file": name, "url": url, "sha256": sha})
                return payload

            if kind == "market":
                observation = BitgetFuturesMarketSource(fetch, self.clock, self.sleep).collect(**parameters)
            else:
                observation = BitgetSettlementSource(fetch, self.clock, self.sleep).collect(**parameters)
            guard()
            count = 25 if kind == "market" else 10
            if len(reads) != count or any(
                    row["url"] != read.url or row["sha256"] != read.response_digest
                    for row, read in zip(reads, observation.reads, strict=True)):
                raise ValueError("complete native source response cohort required")
            sha = _write(fd, "observation.json", observation.record(), MAX_OBSERVATION)
            if sha != observation.data_digest:
                raise ValueError("source observation identity mismatch")
            receipt = {"schema_version": VERSION, "kind": kind, "key": key, "data_digest": sha,
                       "collected_at": observation.collected_at.isoformat(),
                       "responses": reads, "execution_enabled": False}
            # Reparse original native responses before writing the success receipt.
            self._verify(fd, receipt, observation)
            guard()
            receipt_sha = _write(fd, "receipt.json", receipt, MAX_BYTES)
            try:
                os.fsync(fd)
            except OSError:
                raise PaperArchiveCommitUnknown("source cohort acknowledgement unknown") from None
            ref = PaperSourceRef(kind, key, sha, receipt_sha, observation.collected_at)
        except PaperArchiveCommitUnknown:
            object.__setattr__(self, "_uncertain", True)
            raise
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)
        try:
            if self.load(ref) != observation:
                raise ValueError("final source cohort readback mismatch")
        except BaseException:
            object.__setattr__(self, "_uncertain", True)
            raise PaperArchiveCommitUnknown("final source acknowledgement unknown") from None
        return ref, observation

    def load(self, ref):
        if type(ref) is not PaperSourceRef:
            raise ValueError("typed own archive reference required")
        parent = _directory(self.root)
        fd = None
        try:
            fd = os.open(ref.key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            st = os.fstat(fd)
            if st.st_uid != os.getuid() or st.st_mode & 0o777 != 0o700:
                raise ValueError("owned0700 source cohort required")
            raw = _read(fd, "receipt.json", MAX_BYTES)
            if hashlib.sha256(raw).hexdigest() != ref.receipt_digest:
                raise ValueError("source receipt hash mismatch")
            receipt = _fields(decode_json(raw, max_bytes=MAX_BYTES), (
                "schema_version", "kind", "key", "data_digest", "collected_at", "responses", "execution_enabled"))
            if (receipt["schema_version"] != VERSION or receipt["execution_enabled"] is not False
                    or (receipt["kind"], receipt["key"], receipt["data_digest"], receipt["collected_at"]) !=
                    (ref.kind, ref.key, ref.data_digest, ref.collected_at.isoformat())):
                raise ValueError("source receipt context mismatch")
            raw = _read(fd, "observation.json", MAX_OBSERVATION)
            if hashlib.sha256(raw).hexdigest() != ref.data_digest:
                raise ValueError("source observation hash mismatch")
            record = decode_json(raw, max_bytes=MAX_OBSERVATION)
            kind = FuturesMarketObservation if ref.kind == "market" else SettlementEvidence
            observation = _decode(kind, record["observation"])
            if observation.record() != record or observation.data_digest != ref.data_digest:
                raise ValueError("source typed record mismatch")
            self._verify(fd, receipt, observation)
            return observation
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)

    def _verify(self, fd, receipt, observation):
        rows = receipt["responses"]
        count = 25 if receipt["kind"] == "market" else 10
        if type(rows) is not list or len(rows) != count or len(observation.reads) != count:
            raise ValueError("complete archived source cohort required")
        payloads = {}
        for i, (row, read) in enumerate(zip(rows, observation.reads, strict=True), 1):
            _fields(row, ("file", "url", "sha256"))
            if (row["file"] != f"response-{i:02}.json" or row["url"] != read.url
                    or row["sha256"] != read.response_digest or row["url"] in payloads):
                raise ValueError("canonical response/URL/source binding required")
            raw = _read(fd, row["file"], MAX_BYTES)
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("native response hash mismatch")
            payloads[row["url"]] = decode_json(raw, max_bytes=MAX_BYTES)
        # The original response clocks are replayed exactly, without any HTTP.
        clocks = iter((observation.reads[0].requested_at,
                       *(at for row in observation.reads for at in (row.requested_at, row.received_at)),
                       observation.collected_at))
        fetch = lambda url: payloads[url]
        clock = lambda: next(clocks)
        if receipt["kind"] == "market":
            actual = BitgetFuturesMarketSource(fetch, clock, lambda _: None).collect(
                start=observation.start, end=observation.end, funding_start=observation.funding_start)
        else:
            actual = BitgetSettlementSource(fetch, clock, lambda _: None).collect(observation.settled_at)
        if actual != observation:
            raise ValueError("native archive replay differs from typed observation")
