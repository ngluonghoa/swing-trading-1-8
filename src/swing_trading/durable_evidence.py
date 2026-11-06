"""P0.4 local SQLite evidence store, engineering only.

All input payloads must be explicit bytes; never pickle source objects.
Internal checksums are not upstream-source verification.
"""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import sqlite3
from pathlib import Path

from .replay import require_utc

ZERO = "0" * 64


class EvidenceCorrupt(RuntimeError):
    pass


class State(str, Enum):
    STAGED_UNVERIFIED = "STAGED_UNVERIFIED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class EvidenceItem:
    ref: str
    source_id: str
    raw: bytes
    sha256_hex: str
    state: State
    reason: str

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in (
            self.ref, self.source_id, self.reason
        )):
            raise ValueError("Missing audit identifiers")
        if type(self.raw) is not bytes:
            raise TypeError("Raw evidence must be bytes")
        if len(self.raw) > 16 * 1024 * 1024:
            raise ValueError("Raw evidence exceeds bounded fixture size")
        if not isinstance(self.state, State):
            raise TypeError("No VERIFIED state for legacy evidence")
        if sha256(self.raw).hexdigest() != self.sha256_hex:
            raise EvidenceCorrupt("Declared checksum mismatch")


def link(previous, data):
    return sha256((previous + "\n").encode("ascii") + json.dumps(
        data, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


class EvidenceStore:
    """SQLite transaction store. Use a persistent volume outside source control."""

    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()

    def connection(self, writable=False):
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        c = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        if writable:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
        else:
            c.execute("PRAGMA query_only=ON")
        return c

    def initialize(self):
        if self.path.exists():
            raise FileExistsError(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE batches (
                id TEXT PRIMARY KEY, count INTEGER NOT NULL CHECK(count > 0)
            )""")
            c.execute("""CREATE TABLE rows (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                batch TEXT REFERENCES batches(id),
                ref TEXT NOT NULL, source TEXT NOT NULL,
                state TEXT NOT NULL, reason TEXT NOT NULL, payload BLOB NOT NULL,
                sha TEXT NOT NULL, stamped TEXT NOT NULL, prev TEXT NOT NULL,
                chained TEXT NOT NULL, UNIQUE(batch,ref)
            )""")
            for table in ("batches", "rows"):
                for action in ("UPDATE", "DELETE"):
                    c.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                        BEFORE {action} ON {table}
                        BEGIN SELECT RAISE(ABORT, 'append-only'); END""")
            c.execute("PRAGMA user_version=1")
            c.commit()

    def verify(self):
        with closing(self.connection()) as c:
            return self._verify_conn(c)

    @staticmethod
    def _verify_conn(c):
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise EvidenceCorrupt("SQLite failed integrity check")
        if c.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise EvidenceCorrupt("Unsupported schema")
        if c.execute("PRAGMA foreign_key_check").fetchone():
            raise EvidenceCorrupt("Broken relationship")
        for table in ("batches", "rows"):
            for action in ("update", "delete"):
                trigger = table + "_no_" + action
                if c.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?",
                             (trigger,)).fetchone() is None:
                    raise EvidenceCorrupt("Missing append-only trigger")
        count_by_batch = {r["id"]: r["count"] for r in c.execute("SELECT * FROM batches")}
        seen, tip = {}, ZERO
        for r in c.execute("SELECT * FROM rows ORDER BY seq"):
            seen[r["batch"]] = seen.get(r["batch"], 0) + 1
            if tip != r["prev"] or sha256(r["payload"]).hexdigest() != r["sha"]:
                raise EvidenceCorrupt("Raw bytes or previous link changed")
            values = (r["batch"], r["ref"], r["source"], r["state"],
                      r["reason"], r["sha"], r["stamped"])
            if link(tip, values) != r["chained"]:
                raise EvidenceCorrupt("Receipt chain changed")
            tip = r["chained"]
        if count_by_batch != seen:
            raise EvidenceCorrupt("Batch count mismatch")
        return (sum(seen.values()), tip)

    def append_batch(self, batch_id, items, at_utc: datetime, *, expected_tip_sha256=None):
        require_utc(at_utc)
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("Missing batch ID")
        if not isinstance(items, tuple) or not items or len(items) > 1000:
            raise ValueError("Expected bounded nonempty batch")
        if any(not isinstance(x, EvidenceItem) for x in items):
            raise TypeError("Batch must have typed EvidenceItem")
        if len({x.ref for x in items}) != len(items):
            raise ValueError("Duplicate receipt reference")
        stamped = at_utc.isoformat()
        with closing(self.connection(writable=True)) as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                _, tip = self._verify_conn(c)
                if expected_tip_sha256 is not None and expected_tip_sha256 != tip:
                    raise EvidenceCorrupt("Stale chain head or concurrent writer")
                c.execute("INSERT INTO batches VALUES (?,?)", (batch_id, len(items)))
                for item in items:
                    values = (batch_id, item.ref, item.source_id, item.state.value,
                              item.reason, item.sha256_hex, stamped)
                    chained = link(tip, values)
                    c.execute("""INSERT INTO rows (
                        batch,ref,source,state,reason,payload,sha,stamped,prev,chained
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (batch_id, item.ref, item.source_id, item.state.value,
                     item.reason, sqlite3.Binary(item.raw), item.sha256_hex,
                     stamped, tip, chained))
                    tip = chained
                result = self._verify_conn(c)
                c.execute("COMMIT")
                return result
            except Exception:
                c.execute("ROLLBACK")
                raise

    def read_verified_bytes(self, batch_id, row_reference):
        """Read original bytes only after checksums and chain validate."""
        with closing(self.connection()) as c:
            c.execute("BEGIN")
            try:
                self._verify_conn(c)
                r = c.execute("SELECT payload FROM rows WHERE batch=? AND ref=?",
                              (batch_id, row_reference)).fetchone()
                if r is None:
                    raise KeyError((batch_id, row_reference))
                return bytes(r["payload"])
            finally:
                c.execute("ROLLBACK")
