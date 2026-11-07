"""H2-A: audit the complete existing package, not just recently-added modules."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.h2_architecture_audit import analyze, cycles, direct_imports, owner


class ArchitectureInventoryTests(unittest.TestCase):
    def test_inventory_all_existing_modules_and_tests(self):
        result = analyze()
        self.assertGreaterEqual(result["source_module_count"], 61)
        self.assertGreaterEqual(result["test_file_count"], 60)
        self.assertEqual(len(result["modules"]), result["source_module_count"])
        self.assertEqual(len({x["module"] for x in result["modules"]}),
                         result["source_module_count"])
        self.assertEqual(result["schema"], "h2.architecture.inventory.v1")

    def test_static_boundary_gate_no_violations(self):
        report = analyze()
        self.assertEqual(report["violations"], [])
        self.assertTrue(report["passes_static_gate"])

    def test_not_a_runtime_or_source_rights_claim(self):
        report = analyze()
        self.assertFalse(report["source_authorized"])
        self.assertFalse(report["runtime_release_approved"])
        self.assertFalse(report["backtest_oos_verified"])

    def test_deterministic_serialization_and_order(self):
        a = analyze()
        b = analyze()
        self.assertEqual(a, b)
        self.assertEqual(
            [x["module"] for x in a["modules"]],
            sorted(x["module"] for x in a["modules"]),
        )

    def test_all_module_dependencies_resolve(self):
        report = analyze()
        names = {x["module"] for x in report["modules"]}
        for mod in report["modules"]:
            with self.subTest(module=mod["module"]):
                self.assertTrue(set(mod["internal_imports"]) <= names)

    def test_import_cycles_detected(self):
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        self.assertTrue(cycles(graph))
        self.assertEqual(cycles({"a": {"b"}, "b": set()}), ())

    def test_relative_import_and_stdlib_separated(self):
        tree = ast.parse("from .market_data import CanonicalCandle\n"
                         "from . import replay\nimport sqlite3\n"
                         "from swing_trading.contracts import Evidence\n")
        inside, outside = direct_imports(tree, {"market_data", "replay", "contracts"})
        self.assertEqual(inside, {"market_data", "replay", "contracts"})
        self.assertEqual(outside, {"sqlite3"})

    def test_domain_infrastructure_leak_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            tests = root / "tests"
            src.mkdir()
            tests.mkdir()
            (src / "contracts.py").write_text("import sqlite3\n", encoding="utf-8")
            (src / "engineering_contracts.py").write_text("# safe\n", encoding="utf-8")
            report = analyze(src, tests)
            self.assertTrue(any(x.startswith("CORE_IMPORTS_INFRASTRUCTURE")
                                for x in report["violations"]))

    def test_unresolved_internal_import_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            tests = root / "tests"
            src.mkdir()
            tests.mkdir()
            (src / "contracts.py").write_text("from .nonexistent import X\n",
                                              encoding="utf-8")
            (src / "engineering_contracts.py").write_text("# safe\n", encoding="utf-8")
            report = analyze(src, tests)
            self.assertTrue(any(x.startswith("UNRESOLVED_RELATIVE_IMPORT")
                                for x in report["violations"]))

    def test_discarded_c3c_cannot_be_reintroduced(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            tests = root / "tests"
            src.mkdir()
            tests.mkdir()
            (src / "engineering_contracts.py").write_text("# safe\n", encoding="utf-8")
            (tests / "test_drive_c3c_receipt.py").write_text("# not allowed\n",
                                                           encoding="utf-8")
            report = analyze(src, tests)
            self.assertTrue(any("ROLLED_BACK_C3C_REINTRODUCED" in x
                                for x in report["violations"]))

    def test_five_architecture_ownership_areas(self):
        self.assertEqual(owner("segmented_cache"), "cache_and_persistence")
        self.assertEqual(owner("vcbs_source_contract"), "source_adapter_and_quality")
        self.assertEqual(owner("provider_signed_event_chain"), "evidence_and_rights")
        self.assertEqual(owner("engineering_release"), "engineering_governance")
        self.assertEqual(owner("backtest"), "domain_and_reference")


if __name__ == "__main__":
    unittest.main()
