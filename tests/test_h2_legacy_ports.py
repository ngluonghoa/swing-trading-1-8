"""H2-B/C consumer-driven parity against *existing* Swing source/cache/replay code.

All inputs are fabricated, there is no vendor API, Google Drive or broker I/O.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from swing_trading.backtest import BacktestHarness
from swing_trading.causal import CausalMarketEvent
from swing_trading.d1_mcp_transport_bridge import (
    D1ReferenceTransport, ReadOnlyMcpD1Bridge, ProviderSeparatedReferenceCache,
)
from swing_trading.dnse_d1_reference_fallback import D1Provider, D1ReadState
from swing_trading.engineering_contracts import (
    EngineeringPortRegistry, PortDescriptor, require_compatible_port,
)
from swing_trading.incremental_cache import (
    CacheIdentity, FixtureBar, Provider, SyntheticIncrementalStore, full_recompute,
)
from swing_trading.partition_chunk_cache import SyntheticDrivePartitionIndex
from swing_trading.replay import ReplayClock
from swing_trading.segmented_cache import SyntheticWeeklyChunkStore
from swing_trading.contracts import DecisionStatus, SignalDecision, Strategy
from test_d1_mcp_transport_bridge import bridge, ssi_payload, dnse_payload
from test_dnse_d1_reference_fallback import request, NOW as D1_NOW

NOW = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)
START = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
ONE_DAY = timedelta(days=1)


def identity(*, provider=Provider.SSI, indicator="EMA20ATR14"):
    return CacheIdentity(
        provider=provider, endpoint_id="synthetic.d1", instrument_id="FAKE001",
        exchange="HOSE", timeframe="D1", session_id="FAKE.2026.Q1",
        price_basis="RAW", adjustment_revision="ADJ1", calendar_version="VNTEST1",
        aggregation_policy_version="TESTAGG1", indicator_version=indicator,
    )


def bar(day, *, revision="r1", change=False):
    price = Decimal(100 + day)
    if change:
        price = Decimal(175)
    when = START + day * ONE_DAY
    return FixtureBar(
        start_utc=when, end_utc=when + ONE_DAY,
        open=price - 1, high=price + 2, low=price - 2, close=price,
        volume=1000 + day, revision=revision, first_known_utc=when + ONE_DAY,
    )


def provider_ports(*, ssi=None, dnse=None):
    counts = {"SSI": 0, "DNSE": 0}

    def ssi_fake(args):
        counts["SSI"] += 1
        return ssi_payload() if ssi is None else ssi

    def dnse_fake(args):
        counts["DNSE"] += 1
        return dnse_payload() if dnse is None else dnse

    source_ssi = D1ReferenceTransport(
        D1Provider.SSI, "marketdata_list_daily_stock_infor", ssi_fake
    )
    source_dnse = D1ReferenceTransport(
        D1Provider.DNSE, "price_get_history", dnse_fake
    )
    return source_ssi, source_dnse, counts


def typed_bridge(*, ssi=None, dnse=None):
    s, d, counts = provider_ports(ssi=ssi, dnse=dnse)
    b = ReadOnlyMcpD1Bridge.from_transports(
        ssi=s, dnse=d, clock=lambda: D1_NOW - timedelta(minutes=1),
        cache=ProviderSeparatedReferenceCache(),
    )
    return b, counts


class ExistingD1BridgeRetrofitTests(unittest.TestCase):
    def test_typed_source_wiring_does_not_call_transport(self):
        _, counts = typed_bridge()
        self.assertEqual(counts, {"SSI": 0, "DNSE": 0})

    def test_primary_ssi_exact_legacy_reference_parity(self):
        legacy, calls = bridge()
        typed, count = typed_bridge()
        self.assertEqual(typed.run(request()), legacy.run(request()))
        self.assertEqual([name for name, _ in calls], ["SSI"])
        self.assertEqual(count, {"SSI": 1, "DNSE": 0})

    def test_fallback_dnse_exact_legacy_reference_parity(self):
        unavailable = {"status": "error", "error": "DOWNSTREAM_UNAVAILABLE"}
        legacy, calls = bridge(ssi_response=unavailable)
        typed, count = typed_bridge(ssi=unavailable)
        self.assertEqual(typed.run(request()), legacy.run(request()))
        self.assertEqual([name for name, _ in calls], ["SSI", "DNSE"])
        self.assertEqual(count, {"SSI": 1, "DNSE": 1})

    def test_bad_provider_name_cannot_relabel_ssi_callback(self):
        s, d, counts = provider_ports()
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            ReadOnlyMcpD1Bridge.from_transports(
                ssi=d, dnse=s, clock=lambda: D1_NOW, cache=ProviderSeparatedReferenceCache(),
            )
        self.assertEqual(counts, {"SSI": 0, "DNSE": 0})

    def test_wrong_provider_endpoint_denied(self):
        with self.assertRaisesRegex(ValueError, "ENDPOINT_MISMATCH"):
            D1ReferenceTransport(D1Provider.SSI, "price_get_history", lambda _: {})

    def test_source_version_downgrade_or_major_mismatch_denied(self):
        s, d, counts = provider_ports()
        for bad in ("0.9.9", "2.0.0"):
            with self.subTest(version=bad), self.assertRaises(ValueError):
                ReadOnlyMcpD1Bridge.from_transports(
                    ssi=replace(s, version=bad), dnse=d, clock=lambda: D1_NOW,
                    cache=ProviderSeparatedReferenceCache(),
                )
        self.assertEqual(counts, {"SSI": 0, "DNSE": 0})

    def test_source_contract_flags_are_not_authority(self):
        s, _, _ = provider_ports()
        with self.assertRaises(PermissionError):
            replace(s, licensed_market_data_authorized=True)
        with self.assertRaises(PermissionError):
            replace(s, reference_only=False)

    def test_invalid_transport_callback_denied_before_use(self):
        with self.assertRaises(TypeError):
            D1ReferenceTransport(D1Provider.SSI, "marketdata_list_daily_stock_infor",
                                 callback=None)

    def test_explicit_bad_type_denied(self):
        s, d, _ = provider_ports()
        with self.assertRaises(TypeError):
            ReadOnlyMcpD1Bridge.from_transports(
                ssi="SSI", dnse=d, clock=lambda: D1_NOW,
                cache=ProviderSeparatedReferenceCache(),
            )

    def test_typed_port_retains_existing_blocked_state_on_bad_source(self):
        broken = {"status": "ok", "data": {"stocks": "not-list"}}
        typed, _ = typed_bridge(ssi=broken)
        legacy, _ = bridge(ssi_response=broken)
        self.assertEqual(typed.run(request()).audit.state,
                         legacy.run(request()).audit.state)
        self.assertEqual(typed.run(request()).audit.state, D1ReadState.BLOCKED)

    def test_bad_request_mapping_never_invokes_source(self):
        s, _, count = provider_ports()
        with self.assertRaises(TypeError):
            s.fetch_readonly([])
        self.assertEqual(count["SSI"], 0)


class SourceStandIn:
    def __init__(self, events):
        self.events = events
        self.calls = 0

    def available_events(self, as_of_utc):
        self.calls += 1
        return self.events


class NoSignalRules:
    def __init__(self):
        self.calls = 0

    def evaluate(self, zone_id, strategy, as_of_utc):
        self.calls += 1
        return SignalDecision(zone_id, strategy, DecisionStatus.UNVERIFIED)


def replay_descriptors():
    return (
        PortDescriptor("replay.causal_events", "1.0.0", "SYNTHETIC_TEST_ONLY",
                       ("available_events",)),
        PortDescriptor("rules.zone_registry", "1.0.0", "SYNTHETIC_TEST_ONLY",
                       ("evaluate",)),
    )


class ExistingBacktestPortTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 11, 7, tzinfo=timezone.utc)
        self.now = CausalMarketEvent("FAKE1", "r1", self.at, self.at, {"close": "1"})
        self.future = CausalMarketEvent(
            "FAKE1", "r2", self.at, self.at + timedelta(minutes=3), {"close": "2"}
        )
        self.source = SourceStandIn((self.future, self.now))
        self.rules = NoSignalRules()
        self.market_contract, self.rules_contract = replay_descriptors()

    def new_harness(self, market=None, rules=None):
        return BacktestHarness.from_contracts(
            clock=ReplayClock(self.at),
            market_data=self.source,
            market_port=market or self.market_contract,
            rules=self.rules,
            rules_port=rules or self.rules_contract,
        )

    def test_new_constructor_has_identical_first_known_behavior(self):
        old = BacktestHarness(ReplayClock(self.at), self.source, self.rules)
        new = self.new_harness()
        self.assertEqual(new.visible_events(), old.visible_events())
        self.assertEqual(tuple(e.revision_id for e in new.visible_events()), ("r1",))

    def test_constructor_does_not_call_source_or_rules(self):
        self.new_harness()
        self.assertEqual((self.source.calls, self.rules.calls), (0, 0))

    def test_cross_scope_port_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            self.new_harness(market=replace(self.market_contract, scope="SSI"))
        self.assertEqual(self.source.calls, 0)

    def test_rules_version_major_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "INCOMPATIBLE_CONTRACT_VERSION"):
            self.new_harness(rules=replace(self.rules_contract, version="2.0.0"))

    def test_rule_implementation_missing_method_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSING_CALLABLE"):
            BacktestHarness.from_contracts(
                clock=ReplayClock(self.at), market_data=self.source,
                market_port=self.market_contract, rules=object(),
                rules_port=self.rules_contract,
            )

    def test_missing_replay_clock_denied(self):
        with self.assertRaises(TypeError):
            BacktestHarness.from_contracts(
                clock=None, market_data=self.source, market_port=self.market_contract,
                rules=self.rules, rules_port=self.rules_contract,
            )


class ExistingCachePortCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.identity = identity()
        self.bars = tuple(bar(day) for day in range(15))
        self.partition = SyntheticDrivePartitionIndex()
        self.weekly = SyntheticWeeklyChunkStore()
        self.registry = EngineeringPortRegistry()

    def stage(self):
        self.partition.stage_and_publish(
            self.identity, self.bars, expected_head_sha256=None, created_at_utc=NOW
        )
        self.weekly.commit(
            self.identity, self.bars, expected_head=None, observed_at_utc=NOW
        )

    def test_old_backends_implement_same_versioned_read_port(self):
        self.assertEqual(self.partition.read_port_descriptor, self.weekly.read_port_descriptor)
        for backend in (self.partition, self.weekly):
            require_compatible_port(
                self.partition.read_port_descriptor, backend.read_port_descriptor, backend
            )

    def test_same_fixture_identical_consumer_visible_bars(self):
        self.stage()
        expected = self.bars
        for backend in (self.partition, self.weekly):
            with self.subTest(backend=type(backend).__name__):
                self.assertEqual(
                    backend.read_partition(self.identity,
                                           pinned_digest=backend.get_head(self.identity)),
                    expected,
                )

    def test_pinned_consumer_swap_between_existing_c3b_and_c4a(self):
        self.stage()
        required = self.partition.read_port_descriptor
        self.registry.add(required, self.partition)
        self.registry.bind_consumer("replay.scan", required)
        old = self.registry.resolve(required).read_partition(
            self.identity, pinned_digest=self.partition.get_head(self.identity)
        )
        self.registry.replace(required, self.weekly.read_port_descriptor, self.weekly)
        new = self.registry.resolve(required).read_partition(
            self.identity, pinned_digest=self.weekly.get_head(self.identity)
        )
        self.assertEqual(old, new)
        with self.assertRaises(ValueError):
            self.registry.remove(required)

    def test_wrong_provider_is_denied_by_both_legacy_backends(self):
        self.stage()
        other = identity(provider=Provider.DNSE)
        for backend in (self.partition, self.weekly):
            with self.subTest(backend=type(backend).__name__), self.assertRaises(ValueError):
                backend.read_partition(other, pinned_digest=backend.get_head(self.identity))

    def test_wrong_indicator_revision_denied_by_both(self):
        self.stage()
        wrong = identity(indicator="EMA21ATR14")
        for backend in (self.partition, self.weekly):
            with self.subTest(backend=type(backend).__name__), self.assertRaises(ValueError):
                backend.read_partition(wrong, pinned_digest=backend.get_head(self.identity))

    def test_missing_or_bad_head_fails_closed(self):
        self.stage()
        for backend in (self.partition, self.weekly):
            with self.subTest(backend=type(backend).__name__), self.assertRaises(ValueError):
                backend.read_partition(self.identity, pinned_digest="1" * 64)

    def test_crash_before_publish_does_not_replace_existing_head(self):
        self.stage()
        first = {backend: backend.get_head(self.identity)
                 for backend in (self.partition, self.weekly)}
        revised = tuple(bar(day, revision="r2", change=True) if day == 8 else bar(day)
                        for day in range(15))
        with self.assertRaises(RuntimeError):
            self.partition.stage_and_publish(
                self.identity, revised, expected_head_sha256=first[self.partition],
                created_at_utc=NOW, simulate_crash_after_chunk=True,
            )
        with self.assertRaises(RuntimeError):
            self.weekly.commit(
                self.identity, revised, expected_head=first[self.weekly],
                observed_at_utc=NOW, fail_after_staging=True,
            )
        for backend in (self.partition, self.weekly):
            self.assertEqual(backend.get_head(self.identity), first[backend])
            self.assertEqual(backend.read_partition(
                self.identity, pinned_digest=first[backend]), self.bars)

    def test_one_dirty_week_and_global_indicator_recompute_parity(self):
        self.stage()
        revised = tuple(bar(day, revision="r2", change=True) if day == 8 else bar(day)
                        for day in range(15))
        p_head = self.partition.get_head(self.identity)
        w_head = self.weekly.get_head(self.identity)
        self.partition.stage_and_publish(
            self.identity, revised, expected_head_sha256=p_head, created_at_utc=NOW
        )
        outcome = self.weekly.commit(
            self.identity, revised, expected_head=w_head, observed_at_utc=NOW
        )
        self.assertEqual(outcome.created_windows, 1)
        self.assertEqual(
            self.partition.read_partition(self.identity,
                                          pinned_digest=self.partition.get_head(self.identity)),
            self.weekly.read_partition(self.identity,
                                       pinned_digest=self.weekly.get_head(self.identity)),
        )
        with TemporaryDirectory() as tmp:
            local_a = SyntheticIncrementalStore(Path(tmp) / "a.sqlite")
            local_b = SyntheticIncrementalStore(Path(tmp) / "b.sqlite")
            local_a.initialize()
            local_b.initialize()
            self.partition.restore_partition(
                local_a, self.identity,
                pinned_manifest_sha256=self.partition.get_head(self.identity)
            )
            self.weekly.restore_full(
                local_b, self.identity, pinned_head=self.weekly.get_head(self.identity)
            )
            self.assertEqual(local_a.read_bars(self.identity), revised)
            self.assertEqual(local_b.read_bars(self.identity), revised)
            self.assertEqual(local_a.read_checkpoints(self.identity), full_recompute(revised))
            self.assertEqual(local_b.read_checkpoints(self.identity), full_recompute(revised))

    def test_read_port_never_grants_real_market_authority(self):
        self.assertEqual(self.partition.read_port_descriptor.scope, "SYNTHETIC_TEST_ONLY")
        self.assertEqual(self.weekly.read_port_descriptor.scope, "SYNTHETIC_TEST_ONLY")
        with self.assertRaises(ValueError):
            require_compatible_port(
                replace(self.partition.read_port_descriptor, scope="SSI"),
                self.weekly.read_port_descriptor,
                self.weekly,
            )


if __name__ == "__main__":
    unittest.main()
