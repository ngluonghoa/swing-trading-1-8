"""P0.17 opt-in, local-only SSI/DNSE reference journal and bounded diagnostic cache.

This does not connect to MCP, grant a data licence, certify first-known timestamps,
enable signal/backtest inputs, or install a production service.
"""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .d1_mcp_transport_bridge import BridgeRun, ReceiptState
from .dnse_d1_reference_fallback import (
    D1Provider, D1ReadState, D1ReferenceRequest,
)
from .market_data import PriceBasis
from .replay import require_utc

ZERO = "0" * 64
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_TTL = timedelta(days=30)


class ReferenceJournalCorrupt(RuntimeError):
    """Integrity, unexpected schema, or stale-write failure."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(value.encode("utf-8")).hexdigest()


def _utc(value):
    require_utc(value)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Explicit stable ASCII identifier required")
    return value


@dataclass(frozen=True)
class ReferenceRetentionAuthorization:
    """Caller assertions only: NO independently verified legal or host approval."""
    policy_id: str
    expires_at_utc: datetime
    licensed_retention_approved: bool = False
    secured_storage_approved: bool = False

    def __post_init__(self):
        _id(self.policy_id)
        _utc(self.expires_at_utc)
        if (self.licensed_retention_approved is not True
                or self.secured_storage_approved is not True):
            raise PermissionError("Explicit licence AND secure storage approval required")


@dataclass(frozen=True)
class DiagnosticReference:
    """An informational, provider-specific read; NEVER a market-data source."""
    run_id: str
    provider: D1Provider
    symbol: str
    exchange: str
    session_date: str
    observed_at_utc: datetime
    source_digest: str
    vnd_ohlc: tuple[Decimal, Decimal, Decimal, Decimal]
    volume: int
    expires_at_utc: datetime
    price_basis: PriceBasis = PriceBasis.UNKNOWN
    eligible_for_indicators: bool = False
    eligible_for_backtest: bool = False
    actionable: bool = False

    def __post_init__(self):
        if (self.price_basis is not PriceBasis.UNKNOWN
                or self.eligible_for_indicators or self.eligible_for_backtest
                or self.actionable):
            raise ValueError("P0.17 cannot elevate source permissions or evidence")


def _payload(request: D1ReferenceRequest, run: BridgeRun, run_id: str):
    if not isinstance(request, D1ReferenceRequest) or not isinstance(run, BridgeRun):
        raise TypeError("Typed request and nonactionable BridgeRun required")
    _id(run_id)
    receipts = []
    for entry in run.receipts:
        if (entry.symbol != request.symbol or entry.exchange != request.exchange
                or entry.requested_date != request.session_date_local
                or entry.retrieved_at_utc > request.as_of_utc):
            raise ValueError("Receipt identity/date/as-of mismatch")
        receipts.append({
            "provider": entry.provider.value,
            "endpoint": entry.endpoint,
            "retrieved_at_utc": _utc(entry.retrieved_at_utc),
            "state": entry.state.value,
            "source_digest": entry.raw_payload_digest_sha256,
        })
    audit = run.audit
    quote = audit.reference_quote
    if quote is not None:
        if (audit.source is None or quote.provider is not audit.source
                or quote.symbol != request.symbol or quote.exchange != request.exchange
                or quote.session_date_local != request.session_date_local
                or quote.observed_at_utc > request.as_of_utc
                or quote.price_basis is not PriceBasis.UNKNOWN):
            raise ValueError("Selected reference has unqualified/mismatched source")
        matched = [r for r in receipts if
                   r["provider"] == quote.provider.value
                   and r["state"] == ReceiptState.FETCHED.value
                   and r["source_digest"] == quote.source_snapshot_id
                   and r["retrieved_at_utc"] == _utc(quote.observed_at_utc)]
        if len(matched) != 1:
            raise ValueError("Reference must match exactly one fetched source receipt")
    if audit.state is D1ReadState.BLOCKED and quote is not None:
        raise ValueError("Blocked route may not persist a quote")
    body = {
        "run_id": run_id, "symbol": request.symbol, "exchange": request.exchange,
        "session_date": request.session_date_local.isoformat(),
        "timeframe": request.timeframe.value, "as_of_utc": _utc(request.as_of_utc),
        "result_state": audit.state.value, "reason": audit.reason,
        "selected_provider": audit.source.value if audit.source else None,
        "receipts": receipts, "reference_only": True,
        "data_certified": False, "actionable": False,
    }
    return body, quote


def _quote_data(quote):
    return {
        "provider": quote.provider.value, "symbol": quote.symbol,
        "exchange": quote.exchange, "session_date": quote.session_date_local.isoformat(),
        "observed_at_utc": _utc(quote.observed_at_utc),
        "source_digest": quote.source_snapshot_id,
        "endpoint": quote.endpoint, "price_basis": quote.price_basis.value,
        "vnd_ohlc": [format(x, "f") for x in quote.vnd_prices()],
        "volume": quote.volume, "reference_only": True,
    }


class ReferenceJournal:
    """Local SQLite journal: append-only metadata + opt-in, expiring quote cache.

    Caller must supply an approved path on external protected storage. No such
    path, custody, encryption, retention policy or live runtime is provisioned.
    """

    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()

    def initialize(self):
        if self.path.exists():
            raise FileExistsError(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("""CREATE TABLE journal(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL,
                prev TEXT NOT NULL, chained TEXT NOT NULL)""")
            c.execute("""CREATE TABLE cache(
                run_id TEXT PRIMARY KEY REFERENCES journal(run_id),
                provider TEXT NOT NULL CHECK(provider IN ('SSI','DNSE')),
                expiry TEXT NOT NULL, policy_id TEXT NOT NULL,
                quote_json TEXT NOT NULL)""")
            for action in ("UPDATE", "DELETE"):
                c.execute(f"""CREATE TRIGGER journal_no_{action.lower()}
                    BEFORE {action} ON journal
                    BEGIN SELECT RAISE(ABORT, 'append-only'); END""")
            c.execute("PRAGMA user_version=1")
            c.commit()

    def _connection(self, writable=False):
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

    @staticmethod
    def _verify(c):
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ReferenceJournalCorrupt("SQLite integrity failed")
        if c.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ReferenceJournalCorrupt("Unknown journal schema")
        if c.execute("PRAGMA foreign_key_check").fetchone():
            raise ReferenceJournalCorrupt("Broken reference relationship")
        for action in ("update", "delete"):
            name = "journal_no_" + action
            if not c.execute(
                "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
            ).fetchone():
                raise ReferenceJournalCorrupt("Missing append-only protection")
        count, tip = 0, ZERO
        by_run = {}
        for row in c.execute("SELECT * FROM journal ORDER BY seq"):
            count += 1
            if row["seq"] != count or row["prev"] != tip:
                raise ReferenceJournalCorrupt("Journal sequence or link changed")
            try:
                body = json.loads(row["body"])
                if (_json(body) != row["body"]
                        or body["run_id"] != row["run_id"]):
                    raise ValueError("Noncanonical receipt body")
            except (ValueError, KeyError, TypeError) as exc:
                raise ReferenceJournalCorrupt("Invalid receipt body") from exc
            if _hash(tip + "\n" + row["body"]) != row["chained"]:
                raise ReferenceJournalCorrupt("Receipt digest changed")
            by_run[row["run_id"]] = body
            tip = row["chained"]
        for cached in c.execute("SELECT * FROM cache"):
            try:
                body = by_run[cached["run_id"]]
                quote = json.loads(cached["quote_json"])
                if (_json(quote) != cached["quote_json"] or
                    body.get("quote_digest") != _hash(cached["quote_json"]) or
                    body.get("quote_policy") != cached["policy_id"] or
                    body.get("quote_expiry") != cached["expiry"] or
                    body["selected_provider"] != cached["provider"] or
                    quote["provider"] != cached["provider"] or
                    quote["symbol"] != body["symbol"] or
                    quote["exchange"] != body["exchange"] or
                    quote["session_date"] != body["session_date"] or
                    quote["price_basis"] != PriceBasis.UNKNOWN.value or
                    quote["reference_only"] is not True):
                    raise ValueError("Cached reference mismatch")
                if len(quote["vnd_ohlc"]) != 4:
                    raise ValueError("Incomplete diagnostic quote")
                prices = [Decimal(p) for p in quote["vnd_ohlc"]]
                if any(not p.is_finite() or p <= 0 for p in prices):
                    raise ValueError("Invalid cached reference price")
                if type(quote["volume"]) is not int or quote["volume"] < 0:
                    raise ValueError("Invalid cached volume")
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                raise ReferenceJournalCorrupt("Cache integrity or provenance failed") from exc
        return count, tip

    def verify(self):
        with closing(self._connection()) as c:
            c.execute("BEGIN")
            try:
                return self._verify(c)
            finally:
                c.execute("ROLLBACK")

    def append(self, run_id: str, request: D1ReferenceRequest, run: BridgeRun,
               *, expected_tip: str, retention: ReferenceRetentionAuthorization | None = None):
        """Atomic journal+optional cache write. Explicit optimistic chain-head lease."""
        if not isinstance(expected_tip, str) or not _SHA.fullmatch(expected_tip):
            raise ValueError("Explicit expected SHA256 chain tip required")
        body, quote = _payload(request, run, run_id)
        q_json = None
        if retention is not None:
            if not isinstance(retention, ReferenceRetentionAuthorization):
                raise TypeError("Typed retention authorization required")
            if quote is None:
                raise ValueError("No quote to store under authorized retention")
            delta = retention.expires_at_utc - quote.observed_at_utc
            if not timedelta(0) < delta <= _MAX_TTL:
                raise ValueError("Reference expiry must be later than receipt, within 30 days")
            q_json = _json(_quote_data(quote))
            body["quote_digest"] = _hash(q_json)
            body["quote_policy"] = retention.policy_id
            body["quote_expiry"] = _utc(retention.expires_at_utc)
        body_json = _json(body)
        with closing(self._connection(writable=True)) as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                count, tip = self._verify(c)
                if tip != expected_tip:
                    raise ReferenceJournalCorrupt("Stale head; concurrent write or rewrite")
                chained = _hash(tip + "\n" + body_json)
                c.execute("INSERT INTO journal(run_id,body,prev,chained) VALUES (?,?,?,?)",
                          (run_id, body_json, tip, chained))
                if q_json is not None:
                    c.execute("""INSERT INTO cache(run_id,provider,expiry,policy_id,quote_json)
                        VALUES (?,?,?,?,?)""",
                        (run_id, quote.provider.value, body["quote_expiry"],
                         retention.policy_id, q_json))
                result = self._verify(c)
                if result != (count + 1, chained):
                    raise ReferenceJournalCorrupt("Post-write verification failed")
                c.execute("COMMIT")
                return result
            except Exception:
                c.execute("ROLLBACK")
                raise

    def read_diagnostic(self, *, run_id: str, provider: D1Provider,
                        as_of_utc: datetime) -> DiagnosticReference | None:
        """Explicit provider/run and as-of; never an SSI/DNSE adapter fallback."""
        _id(run_id)
        if not isinstance(provider, D1Provider):
            raise TypeError("Provider namespace required")
        cutoff = _utc(as_of_utc)
        with closing(self._connection()) as c:
            c.execute("BEGIN")
            try:
                self._verify(c)
                row = c.execute("""SELECT cache.*, journal.body FROM cache
                    JOIN journal USING (run_id) WHERE cache.run_id=? AND cache.provider=?""",
                    (run_id, provider.value)).fetchone()
                if row is None:
                    return None
                body = json.loads(row["body"])
                quote = json.loads(row["quote_json"])
                if (body["as_of_utc"] > cutoff or
                        quote["observed_at_utc"] > cutoff or
                        row["expiry"] <= cutoff):
                    return None
                return DiagnosticReference(
                    run_id, provider, quote["symbol"], quote["exchange"],
                    quote["session_date"], datetime.fromisoformat(quote["observed_at_utc"]),
                    quote["source_digest"], tuple(Decimal(v) for v in quote["vnd_ohlc"]),
                    quote["volume"], datetime.fromisoformat(row["expiry"]),
                )
            finally:
                c.execute("ROLLBACK")

    def prune_expired(self, *, now_utc: datetime) -> int:
        """Erase expired diagnostic quotes, retaining immutable metadata trail."""
        stamp = _utc(now_utc)
        with closing(self._connection(writable=True)) as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                self._verify(c)
                deleted = c.execute("DELETE FROM cache WHERE expiry <= ?", (stamp,)).rowcount
                self._verify(c)
                c.execute("COMMIT")
                return deleted
            except Exception:
                c.execute("ROLLBACK")
                raise
