"""Consumer-driven replacement contracts. Fake inputs only; no live market calls."""
from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from swing_trading.backtest import BacktestHarness
from swing_trading.causal import CausalMarketEvent
from swing_trading.contracts import (
    DecisionStatus, SignalDecision, Strategy, ZONE_IDS,
)
from swing_trading.engine import evaluate_unimplemented_zones
from swing_trading.engineering_contracts import (
    PortCompatibility, PortDescriptor, check_port, require_compatible_port,
)
from swing_trading.incremental_cache import CacheIdentity, FixtureBar, Provider
from swing_trading.partition_chunk_cache import (
    decode_fixture_chunk, encode_fixture_chunk, require_real_market_cache_transport,
)
from swing_trading.replay import ReplayClock
from swing_trading.segmented_cache import require_authorized_window_cache

T0 = datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc)
SOURCE = Path(__file__).resolve().parents[1] / "src" / "swing_trading"
CORE = {"contracts", "market_data", "causal", "replay", "engine", "backtest"}


class DummySource:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.calls = 0

    def fetch_readonly(self, request: str) -> tuple[str, str]:
        self.calls += 1
        return self.provider, request


class DummyRules:
    def evaluate(self, zone_id, strategy, as_of_utc):
        return SignalDecision(zone_id, strategy, DecisionStatus.UNVERIFIED)


class CausalSource:
    def __init__(self, observations):
        self.observations = observations
        self.calls = 0

    def available_events(self, as_of_utc):
        self.calls += 1
        return self.observations


def descriptor(*, scope="SSI", version="1.0.0", operations=("fetch_readonly",),
               contract_id="source.ohlcv") -> PortDescriptor:
    return PortDescriptor(contract_id, version, scope, operations)


def identity(provider=Provider.SSI, *, indicator="EMA20.ATR14.V1") -> CacheIdentity:
    return CacheIdentity(
        provider=provider, endpoint_id="TEST", instrument_id="TEST001",
        exchange="HOSE", timeframe="M5", session_id="TEST_SESSION",
        price_basis="RAW", adjustment_revision="ADJ1", calendar_version="CAL1",
        aggregation_policy_version="AGG1", indicator_version=indicator,
    )


def fake_bar(*, closed=True) -> FixtureBar:
    return FixtureBar(
        start_utc=T0, end_utc=T0 + timedelta(minutes=5),
        open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
        close=Decimal("101"), volume=1000, revision="FAKE1",
        first_known_utc=T0 + timedelta(minutes=5), closed=closed,
    )


class PortDescriptorContractTests(unittest.TestCase):
    def setUp(self):
        self.ssi = DummySource("SSI")
        self.required = descriptor()

    def test_same_version_compatible(self):
        r = check_port(self.required, descriptor(), self.ssi)
        self.assertTrue(r.compatible)
        self.assertEqual(r.reasons, ())
        self.assertTrue(r.structural_only)
        self.assertFalse(r.trading_authorized)

    def test_compatible_new_minor_version(self):
        self.assertTrue(check_port(self.required, descriptor(version="1.4.0"), self.ssi).compatible)

    def test_compatible_new_patch_version(self):
        self.assertTrue(check_port(self.required, descriptor(version="1.0.1"), self.ssi).compatible)

    def test_breaking_major_rejected(self):
        result = check_port(self.required, descriptor(version="2.0.0"), self.ssi)
        self.assertIn("INCOMPATIBLE_CONTRACT_VERSION", result.reasons)

    def test_lower_minor_rejected(self):
        result = check_port(descriptor(version="1.2.0"), descriptor(version="1.1.9"), self.ssi)
        self.assertFalse(result.compatible)

    def test_lower_patch_rejected(self):
        result = check_port(descriptor(version="1.0.4"), descriptor(version="1.0.3"), self.ssi)
        self.assertFalse(result.compatible)

    def test_contract_name_change_rejected(self):
        result = check_port(self.required, descriptor(contract_id="calendar.read"), self.ssi)
        self.assertIn("CONTRACT_ID_MISMATCH", result.reasons)

    def test_cross_provider_substitution_rejected(self):
        result = check_port(self.required, descriptor(scope="DNSE"), DummySource("DNSE"))
        self.assertIn("SCOPE_MISMATCH_NO_IMPLICIT_PROVIDER_FALLBACK", result.reasons)

    def test_missing_operation_rejected(self):
        result = check_port(self.required, descriptor(operations=("health",)), self.ssi)
        self.assertIn("UNDECLARED_OPERATION:fetch_readonly", result.reasons)

    def test_declared_but_noncallable_rejected(self):
        result = check_port(self.required, descriptor(), object())
        self.assertIn("MISSING_CALLABLE:fetch_readonly", result.reasons)

    def test_no_user_code_invoked_during_structural_preflight(self):
        check_port(self.required, descriptor(), self.ssi)
        self.assertEqual(self.ssi.calls, 0)

    def test_explicit_injected_provider_replacement_all_three_namespaces(self):
        for provider in ("SSI", "DNSE", "VCBS"):
            with self.subTest(provider=provider):
                stub = DummySource(provider)
                required = descriptor(scope=provider)
                require_compatible_port(required, descriptor(scope=provider), stub)
                self.assertEqual(stub.fetch_readonly("TEST"), (provider, "TEST"))
                self.assertEqual(stub.calls, 1)

    def test_replacement_requires_explicit_provider_scope(self):
        with self.assertRaisesRegex(ValueError, "SCOPE_MISMATCH"):
            require_compatible_port(self.required, descriptor(scope="VCBS"), DummySource("VCBS"))

    def test_duplicate_operations_rejected(self):
        with self.assertRaises(ValueError):
            descriptor(operations=("fetch_readonly", "fetch_readonly"))

    def test_mutable_operations_rejected(self):
        with self.assertRaises(TypeError):
            descriptor(operations=["fetch_readonly"])

    def test_bad_semver_and_name_rejected(self):
        for version in ("1", "v1.0.0", "1.0", "01.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                descriptor(version=version)
        with self.assertRaises(ValueError):
            descriptor(contract_id="../source")
        with self.assertRaises(ValueError):
            descriptor(scope="ssi")

    def test_report_cannot_grant_authorization(self):
        with self.assertRaises(PermissionError):
            replace(check_port(self.required, descriptor(), self.ssi), trading_authorized=True)
        with self.assertRaises(PermissionError):
            PortCompatibility(True, (), deploy_authorized=True)

    def test_inconsistent_report_rejected(self):
        with self.assertRaises(ValueError):
            PortCompatibility(True, ("FAILED",))
        with self.assertRaises(ValueError):
            PortCompatibility(False, ())

    def test_untyped_descriptor_rejected(self):
        with self.assertRaises(TypeError):
            check_port(self.required, "source.ohlcv", self.ssi)


class ConsumerReplacementTests(unittest.TestCase):
    def test_swappable_market_data_ports_keep_causal_result(self):
        visible = CausalMarketEvent("fake", "r1", T0, T0, {"close": "100"})
        future = CausalMarketEvent("fake", "r2", T0, T0 + timedelta(minutes=8),
                                   {"close": "105"})
        for source in (CausalSource((visible, future)), CausalSource((future, visible))):
            with self.subTest(source=source.observations):
                harness = BacktestHarness(ReplayClock(T0), source, DummyRules())
                self.assertEqual(tuple(e.revision_id for e in harness.visible_events()), ("r1",))
                self.assertEqual(source.calls, 1)

    def test_untyped_replacement_source_fails_closed(self):
        harness = BacktestHarness(ReplayClock(T0), CausalSource(("not-event",)), DummyRules())
        with self.assertRaises(TypeError):
            harness.visible_events()

    def test_swappable_registry_never_upgrades_unimplemented_detector(self):
        registry = DummyRules()
        for zone in ZONE_IDS:
            r = registry.evaluate(zone, Strategy.SWING, T0)
            self.assertIs(r.status, DecisionStatus.UNVERIFIED)
        for r in evaluate_unimplemented_zones(Strategy.SHORT, T0):
            self.assertIs(r.status, DecisionStatus.UNVERIFIED)

    def test_cache_codec_readback_same_partition(self):
        key = identity()
        encoded = encode_fixture_chunk(key, (fake_bar(),))
        self.assertEqual(decode_fixture_chunk(encoded, expected_identity=key), (fake_bar(),))
        self.assertEqual(encoded, encode_fixture_chunk(key, (fake_bar(),)))

    def test_cache_replacement_cannot_mix_ssi_dnse_vcbs(self):
        data = encode_fixture_chunk(identity(), (fake_bar(),))
        for provider in (Provider.DNSE, Provider.VCBS):
            with self.subTest(provider=provider), self.assertRaises(ValueError):
                decode_fixture_chunk(data, expected_identity=identity(provider))

    def test_cache_schema_or_indicator_version_mismatch_rejected(self):
        data = encode_fixture_chunk(identity(), (fake_bar(),))
        with self.assertRaises(ValueError):
            decode_fixture_chunk(data, expected_identity=identity(indicator="EMA21.ATR14.V2"))

    def test_corrupted_chunk_rejected(self):
        data = encode_fixture_chunk(identity(), (fake_bar(),))
        with self.assertRaises(ValueError):
            decode_fixture_chunk(data + b"CORRUPT", expected_identity=identity())

    def test_open_bars_not_encoded(self):
        with self.assertRaises(ValueError):
            encode_fixture_chunk(identity(), (fake_bar(closed=False),))

    def test_real_cache_adapters_still_unavailable(self):
        with self.assertRaises(PermissionError):
            require_real_market_cache_transport()
        with self.assertRaises(PermissionError):
            require_authorized_window_cache()


class ArchitectureBoundaryTests(unittest.TestCase):
    @staticmethod
    def imports(module: str) -> set[str]:
        tree = ast.parse((SOURCE / (module + ".py")).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 1 and node.module:
                    imports.add(node.module.split(".", 1)[0])
                elif node.level == 0 and node.module and node.module.startswith("swing_trading."):
                    imports.add(node.module.split(".")[1])
                elif node.level == 0 and node.module:
                    imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
        return imports

    def test_core_does_not_import_infrastructure_or_providers(self):
        forbidden = {"sqlite3", "requests", "httpx", "googleapiclient", "boto3",
                     "d1_mcp_transport_bridge", "incremental_cache",
                     "segmented_cache", "partition_chunk_cache", "dnse_d1_reference_fallback",
                     "adaptive_source_router", "vcbs_source_contract"}
        for module in CORE:
            with self.subTest(module=module):
                self.assertFalse(self.imports(module) & forbidden)

    def test_core_import_graph_has_no_cycles(self):
        edges = {module: self.imports(module) & CORE for module in CORE}
        visited = set()
        active = set()

        def visit(module):
            if module in active:
                raise AssertionError("Domain cycle detected at " + module)
            if module in visited:
                return
            active.add(module)
            for dependency in edges[module]:
                visit(dependency)
            active.remove(module)
            visited.add(module)

        for module in sorted(CORE):
            visit(module)


    def test_all_package_modules_have_acyclic_internal_import_graph(self):
        modules = {file.stem for file in SOURCE.glob("*.py")}
        edges = {module: self.imports(module) & modules for module in modules}
        visited = set()
        stack = []

        def visit(module):
            if module in stack:
                raise AssertionError("Internal import cycle: " + " -> ".join(stack + [module]))
            if module in visited:
                return
            stack.append(module)
            for dependency in sorted(edges[module]):
                visit(dependency)
            stack.pop()
            visited.add(module)

        for module in sorted(modules):
            visit(module)

    def test_old_c3c_artifacts_not_reintroduced(self):
        for name in ("drive_c3c_receipt.py",):
            self.assertFalse((SOURCE / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
