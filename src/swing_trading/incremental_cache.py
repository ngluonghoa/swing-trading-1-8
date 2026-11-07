"""OFFLINE SYNTHETIC-ONLY incremental candle and EMA/ATR checkpoint cache.

No real SSI/DNSE quotes may be passed into this store. There is NO runtime
licence gate, approved production host, source adapter, or trading authority.
The class exists to test the architecture and cold/warm/revision equivalence.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .cache_fetch_planner import SourceCursor, _utc

_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SCHEMA = 1
_EMA_SPAN = 20
_ATR_SPAN = 14


def _d(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Finite Decimal required")
    return str(value)


def _parse_utc(s: str) -> datetime:
    return _utc(datetime.fromisoformat(s))


def _canon(v: object) -> str:
    return json.dumps(v, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
                      allow_nan=False)


def _sha(v: object) -> str:
    return sha256(_canon(v).encode("utf-8")).hexdigest()


class Provider(str, Enum):
    SSI = "SSI"
    DNSE = "DNSE"


@dataclass(frozen=True)
class CacheIdentity:
    provider: Provider
    endpoint_id: str
    instrument_id: str
    exchange: str
    timeframe: str
    session_id: str
    price_basis: str
    adjustment_revision: str
    calendar_version: str
    aggregation_policy_version: str
    indicator_version: str
    source_rights_policy_version: str = "RIGHTS.UNVERIFIED"
    source_resolution_policy_version: str = "RESOLUTION.UNVERIFIED"
    quality_policy_version: str = "QUALITY.UNVERIFIED"
    indicator_parameter_version: str = "EMA20.ATR14.SYNTHETIC"
    project_id: str = "SwingTrading1.8"
    environment: str = "SYNTHETIC_TEST_ONLY"

    def __post_init__(self) -> None:
        if type(self.provider) is not Provider or self.project_id != "SwingTrading1.8":
            raise ValueError("Only canonical provider and Swing Trading project permitted")
        if self.environment != "SYNTHETIC_TEST_ONLY":
            raise PermissionError("Real market data persistence is NOT authorized")
        for field, val in asdict(self).items():
            if field == "provider":
                continue
            if not isinstance(val, str) or not _IDENT.fullmatch(val):
                raise ValueError("Invalid version/identity field: " + field)

    @property
    def fingerprint(self) -> str:
        return _sha({**asdict(self), "provider": self.provider.value})


@dataclass(frozen=True)
class FixtureBar:
    """A fabricated OHLCV observation; it must NEVER contain actual market data."""
    start_utc: datetime
    end_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    revision: str
    first_known_utc: datetime
    closed: bool = True

    def __post_init__(self) -> None:
        start, end, known = (_utc(x) for x in
                             (self.start_utc, self.end_utc, self.first_known_utc))
        if end <= start or known < start:
            raise ValueError("Invalid bar or first-known chronology")
        for p in (self.open, self.high, self.low, self.close):
            if not isinstance(p, Decimal) or not p.is_finite() or p < 0:
                raise ValueError("Nonnegative finite Decimal OHLC required")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid OHLC order")
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError("Nonnegative integer matched volume required")
        if not isinstance(self.revision, str) or not _IDENT.fullmatch(self.revision):
            raise ValueError("Opaque revision required")
        if type(self.closed) is not bool:
            raise TypeError("Explicit closed flag required")

    @property
    def normalized_digest(self) -> str:
        return _sha({"start":_utc(self.start_utc).isoformat(timespec="microseconds"), "end":_utc(self.end_utc).isoformat(timespec="microseconds"),
                     "open":_d(self.open),"high":_d(self.high),"low":_d(self.low),
                     "close":_d(self.close),"volume":self.volume,"closed":self.closed})


@dataclass(frozen=True)
class IndicatorCheckpoint:
    start_utc: datetime
    ema20: Decimal
    atr14: Decimal | None
    atr_seen: int
    atr_seed_sum: Decimal
    last_close: Decimal


@dataclass(frozen=True)
class CacheUpdate:
    inserted: int
    revised: int
    deleted: int
    unchanged: int
    lineage_only: int
    ignored_open: int
    indicator_bars_recomputed: int
    first_dirty_utc: datetime | None
    last_closed_utc: datetime | None
    invalidated_layers: tuple[str, ...]
    fixture_only: bool = True
    market_authorized: bool = False


class SyntheticIncrementalStore:
    """Explicit opt-in *fixture* SQLite store; never connects to any market API.

    Callers control the filesystem; security, quotas, encryption, backups and
    SQLite filesystem semantics are NOT verified or approved for live use.
    """
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.parent.is_dir():
            raise ValueError("Parent directory must exist; no automatic deployment")
        if self.path.is_symlink():
            raise ValueError("Symlink path disallowed")

    def _connect(self):
        c = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def initialize(self) -> None:
        with closing(self._connect()) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS config (name TEXT PRIMARY KEY, val TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS fixture_bars (
                    cache_key TEXT NOT NULL, start_utc TEXT NOT NULL, end_utc TEXT NOT NULL,
                    o TEXT NOT NULL, h TEXT NOT NULL, l TEXT NOT NULL, c TEXT NOT NULL,
                    volume INTEGER NOT NULL, revision TEXT NOT NULL,
                    first_known_utc TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(cache_key,start_utc));
                CREATE TABLE IF NOT EXISTS fixture_checkpoints (
                    cache_key TEXT NOT NULL,start_utc TEXT NOT NULL,
                    ema20 TEXT NOT NULL,atr14 TEXT,atr_seen INTEGER NOT NULL,
                    atr_seed_sum TEXT NOT NULL,last_close TEXT NOT NULL,
                    PRIMARY KEY(cache_key,start_utc));
                CREATE TABLE IF NOT EXISTS fixture_cursor (
                    cache_key TEXT PRIMARY KEY,last_checked_utc TEXT NOT NULL,
                    last_full_reconciled_utc TEXT);
                CREATE TABLE IF NOT EXISTS fixture_lineage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,cache_key TEXT NOT NULL,
                    start_utc TEXT NOT NULL,event_type TEXT NOT NULL,
                    old_digest TEXT,new_digest TEXT,observed_at_utc TEXT NOT NULL);
            """)
            row = c.execute("SELECT val FROM config WHERE name='schema'").fetchone()
            if row is None:
                c.execute("INSERT INTO config(name,val) VALUES('schema',?)", (str(_SCHEMA),))
            elif row[0] != str(_SCHEMA):
                raise RuntimeError("Unknown fixture cache schema; explicit migration required")

    def _require_schema(self, c) -> None:
        row = c.execute("SELECT val FROM config WHERE name='schema'").fetchone()
        if row is None or row[0] != str(_SCHEMA):
            raise RuntimeError("Missing or incompatible cache schema")

    @staticmethod
    def _bar(row: sqlite3.Row) -> FixtureBar:
        b = FixtureBar(_parse_utc(row["start_utc"]),_parse_utc(row["end_utc"]),
                       Decimal(row["o"]),Decimal(row["h"]),Decimal(row["l"]),
                       Decimal(row["c"]),row["volume"],row["revision"],
                       _parse_utc(row["first_known_utc"]))
        if b.normalized_digest != row["digest"]:
            raise RuntimeError("Stored fixture candle content digest mismatch")
        return b

    def read_bars(self, identity: CacheIdentity) -> tuple[FixtureBar, ...]:
        with closing(self._connect()) as c:
            self._require_schema(c)
            return tuple(self._bar(x) for x in c.execute(
                "SELECT * FROM fixture_bars WHERE cache_key=? ORDER BY start_utc",(identity.fingerprint,)))

    def read_checkpoints(self, identity: CacheIdentity) -> tuple[IndicatorCheckpoint, ...]:
        with closing(self._connect()) as c:
            self._require_schema(c)
            return tuple(IndicatorCheckpoint(_parse_utc(x["start_utc"]),Decimal(x["ema20"]),
                     Decimal(x["atr14"]) if x["atr14"] is not None else None,
                     x["atr_seen"],Decimal(x["atr_seed_sum"]),Decimal(x["last_close"]))
                     for x in c.execute("SELECT * FROM fixture_checkpoints WHERE cache_key=? ORDER BY start_utc",(identity.fingerprint,)))

    def cursor(self, identity: CacheIdentity) -> SourceCursor | None:
        with closing(self._connect()) as c:
            self._require_schema(c)
            row = c.execute("SELECT * FROM fixture_cursor WHERE cache_key=?",(identity.fingerprint,)).fetchone()
            latest = c.execute("SELECT MAX(start_utc) FROM fixture_bars WHERE cache_key=?",(identity.fingerprint,)).fetchone()[0]
            if row is None or latest is None:
                return None
            return SourceCursor(_parse_utc(latest),_parse_utc(row["last_checked_utc"]),
                                _parse_utc(row["last_full_reconciled_utc"]) if row["last_full_reconciled_utc"] else None)

    def apply_fixture_window(self, identity: CacheIdentity, observations: tuple[FixtureBar, ...], *,
                             observed_at_utc: datetime, scope_start_utc: datetime,
                             scope_end_utc: datetime, complete_scope: bool,
                             full_session_reconciled: bool = False) -> CacheUpdate:
        """Transactional append/correct/delete and minimal-tail indicator replay.

        `complete_scope` authorizes deletion of absent fixture rows ONLY within
        the explicitly bounded returned window; partial API pages MUST be false.
        No live API, rights flags, or source certification can be inferred.
        """
        now,start,end = (_utc(x) for x in (observed_at_utc,scope_start_utc,scope_end_utc))
        if start >= end or end > now or not isinstance(identity,CacheIdentity):
            raise ValueError("Expected typed identity and completed observation window")
        if not isinstance(observations,tuple) or any(not isinstance(x,FixtureBar) for x in observations):
            raise TypeError("Immutable tuple of synthetic fixtures required")
        if type(complete_scope) is not bool or type(full_session_reconciled) is not bool:
            raise TypeError("Scope completeness and reconciliation must be booleans")
        if full_session_reconciled and not complete_scope:
            raise ValueError("Cannot certify full scope with incomplete fixture response")
        if full_session_reconciled and start > min((b.start_utc for b in observations),default=start):
            raise ValueError("Full scope must include observed start")
        seen = set()
        previous = None
        for b in observations:
            if previous is not None and b.start_utc <= previous:
                raise ValueError("Out-of-order or duplicate fixture bars")
            previous = b.start_utc
            if not start <= b.start_utc < end or b.first_known_utc > now:
                raise ValueError("Outside request window or unknown at observation clock")
            if b.closed and b.end_utc > now:
                raise ValueError("Cannot persist a bar before it actually closes")
            seen.add(b.start_utc.isoformat())
        key = identity.fingerprint
        inserted = revised = deleted = unchanged = lineage_only = ignored_open = 0
        dirty: datetime | None = None
        recomputed = 0
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                self._require_schema(c)
                current = {x["start_utc"]:x for x in c.execute(
                    "SELECT * FROM fixture_bars WHERE cache_key=?",(key,))}
                # A stale revision of history may be re-observed: lineage is retained.
                for b in observations:
                    if not b.closed:
                        ignored_open += 1
                        continue
                    stamp = b.start_utc.isoformat()
                    old = current.get(stamp)
                    digest = b.normalized_digest
                    if old is not None and b.first_known_utc < _parse_utc(old["first_known_utc"]):
                        raise ValueError("Source observation first-known cannot move backwards")
                    if old is not None and old["digest"] == digest:
                        # Metadata-only revision: retain append-only evidence, skip L2 replay.
                        if (old["revision"] != b.revision or
                                old["first_known_utc"] != b.first_known_utc.isoformat()):
                            c.execute("UPDATE fixture_bars SET revision=?,first_known_utc=? WHERE cache_key=? AND start_utc=?",
                                      (b.revision,b.first_known_utc.isoformat(),key,stamp))
                            c.execute("INSERT INTO fixture_lineage(cache_key,start_utc,event_type,old_digest,new_digest,observed_at_utc) VALUES (?,?,?,?,?,?)",
                                      (key,stamp,"LINEAGE_ONLY",digest,digest,now.isoformat()))
                            lineage_only += 1
                        else:
                            unchanged += 1
                        continue
                    if old is None:
                        inserted += 1
                        event = "APPEND" if not current or stamp > max(current) else "BACKFILL"
                    else:
                        revised += 1
                        event = "REVISE"
                    dirty = min(dirty,b.start_utc) if dirty is not None else b.start_utc
                    c.execute("""INSERT OR REPLACE INTO fixture_bars
                        (cache_key,start_utc,end_utc,o,h,l,c,volume,revision,first_known_utc,digest)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (key,stamp,b.end_utc.isoformat(),_d(b.open),_d(b.high),_d(b.low),
                         _d(b.close),b.volume,b.revision,b.first_known_utc.isoformat(),digest))
                    c.execute("INSERT INTO fixture_lineage(cache_key,start_utc,event_type,old_digest,new_digest,observed_at_utc) VALUES (?,?,?,?,?,?)",
                              (key,stamp,event,old["digest"] if old else None,digest,now.isoformat()))
                if complete_scope:
                    for stamp,old in current.items():
                        bstart = _parse_utc(stamp)
                        if start <= bstart < end and stamp not in seen:
                            deleted += 1
                            dirty = min(dirty,bstart) if dirty is not None else bstart
                            c.execute("DELETE FROM fixture_bars WHERE cache_key=? AND start_utc=?",(key,stamp))
                            c.execute("INSERT INTO fixture_lineage(cache_key,start_utc,event_type,old_digest,new_digest,observed_at_utc) VALUES (?,?,?,?,?,?)",
                                      (key,stamp,"DELETE",old["digest"],None,now.isoformat()))
                if dirty is not None:
                    c.execute("DELETE FROM fixture_checkpoints WHERE cache_key=? AND start_utc>=?",(key,dirty.isoformat()))
                    preceding = c.execute("SELECT * FROM fixture_checkpoints WHERE cache_key=? AND start_utc<? ORDER BY start_utc DESC LIMIT 1",
                                          (key,dirty.isoformat())).fetchone()
                    state = (IndicatorCheckpoint(_parse_utc(preceding["start_utc"]),Decimal(preceding["ema20"]),
                              Decimal(preceding["atr14"]) if preceding["atr14"] is not None else None,
                              preceding["atr_seen"],Decimal(preceding["atr_seed_sum"]),Decimal(preceding["last_close"])) if preceding else None)
                    for row in c.execute("SELECT * FROM fixture_bars WHERE cache_key=? AND start_utc>=? ORDER BY start_utc",
                                         (key,dirty.isoformat())).fetchall():
                        b = self._bar(row)
                        state = advance_checkpoint(b,state)
                        c.execute("INSERT INTO fixture_checkpoints(cache_key,start_utc,ema20,atr14,atr_seen,atr_seed_sum,last_close) VALUES(?,?,?,?,?,?,?)",
                                  (key,b.start_utc.isoformat(),_d(state.ema20),
                                   _d(state.atr14) if state.atr14 is not None else None,
                                   state.atr_seen,_d(state.atr_seed_sum),_d(state.last_close)))
                        recomputed += 1
                prior = c.execute("SELECT * FROM fixture_cursor WHERE cache_key=?",(key,)).fetchone()
                if prior is not None and _parse_utc(prior["last_checked_utc"]) > now:
                    raise ValueError("Cannot regress cache observation clock")
                last_full = (now.isoformat() if full_session_reconciled else
                             prior["last_full_reconciled_utc"] if prior else None)
                c.execute("""INSERT INTO fixture_cursor(cache_key,last_checked_utc,last_full_reconciled_utc)
                    VALUES(?,?,?) ON CONFLICT(cache_key) DO UPDATE SET
                    last_checked_utc=excluded.last_checked_utc,
                    last_full_reconciled_utc=excluded.last_full_reconciled_utc""",
                          (key,now.isoformat(),last_full))
                latest = c.execute("SELECT MAX(start_utc) FROM fixture_bars WHERE cache_key=?",(key,)).fetchone()[0]
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        layers = ("L1","L2","L3","L4","L5") if dirty is not None else ()
        return CacheUpdate(inserted,revised,deleted,unchanged,lineage_only,ignored_open,
                           recomputed,dirty,_parse_utc(latest) if latest else None,layers)


def advance_checkpoint(bar: FixtureBar, prior: IndicatorCheckpoint | None) -> IndicatorCheckpoint:
    """Deterministic, causal EMA20 and Wilder ATR14 on a *closed fixture* bar."""
    if not bar.closed:
        raise ValueError("OPEN candle cannot alter durable indicator checkpoint")
    ema = bar.close if prior is None else (
        (Decimal(2)*bar.close + Decimal(_EMA_SPAN-1)*prior.ema20) / Decimal(_EMA_SPAN+1))
    tr = (bar.high-bar.low if prior is None else
          max(bar.high-bar.low,abs(bar.high-prior.last_close),abs(bar.low-prior.last_close)))
    seen = 1 if prior is None else prior.atr_seen+1
    seed = (Decimal(0) if prior is None else prior.atr_seed_sum)
    if seen <= _ATR_SPAN:
        seed += tr
    if seen < _ATR_SPAN:
        atr = None
    elif seen == _ATR_SPAN:
        atr = seed / Decimal(_ATR_SPAN)
    else:
        if prior is None or prior.atr14 is None:
            raise RuntimeError("Missing ATR checkpoint seed")
        atr = (prior.atr14*Decimal(_ATR_SPAN-1)+tr)/Decimal(_ATR_SPAN)
    return IndicatorCheckpoint(bar.start_utc,ema,atr,seen,seed,bar.close)


def full_recompute(bars: tuple[FixtureBar,...]) -> tuple[IndicatorCheckpoint,...]:
    """Independent cold/reference path for equivalence tests; not real BT."""
    checkpoints = []
    last = None
    for bar in bars:
        last = advance_checkpoint(bar,last)
        checkpoints.append(last)
    return tuple(checkpoints)


def invalidation_preview(kind: str) -> tuple[str,...]:
    """Dependency-only proposal, not the unimplemented L3/L4/L5 engines."""
    return {
        "BAR_CHANGED": ("L1","L2","L3","L4","L5"),
        "CALENDAR_CHANGED": ("L1","L2","L3","L4","L5"),
        "CORPORATE_ACTION": ("L1","L2","L3","L4","L5"),
        "INDEX_OR_SECTOR": ("L2","L3","L4","L5"),
        "INDICATOR_VERSION": ("L2","L3","L4","L5"),
        "RULE_OR_PARAMETER": ("L4","L5"),
        "POSITION": ("L4","L5"),
        "UI_ONLY": ("L5",),
        "NO_CHANGE": (),
    }[kind]
