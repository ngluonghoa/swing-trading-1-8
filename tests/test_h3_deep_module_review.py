"""H3 static review tests: complete source inventory and honest limitations."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.h3_deep_module_review import (
    analyze_deep, render_matrix, _functions, _duplicates,
)
import ast


class H3ReviewTests(unittest.TestCase):
    def test_entire_original_package_reviewed(self):
        report = analyze_deep()
        self.assertGreaterEqual(report["module_count"], 63)
        self.assertEqual(len(report["modules"]), report["module_count"])
        self.assertEqual(len({m["module"] for m in report["modules"]}),
                         report["module_count"])
        self.assertEqual(report["architecture_violations"], [])
        self.assertTrue(report["passes_architecture_gate"])

    def test_each_module_classified_but_no_auto_replace_or_remove(self):
        report = analyze_deep()
        for m in report["modules"]:
            with self.subTest(module=m["module"]):
                self.assertIn(m["provisional_action"], ("KEEP", "IMPROVE"))
                self.assertFalse(m["human_review_completed"])
                self.assertFalse(m["replacement_authorized"])
                self.assertFalse(m["removal_authorized"])
                self.assertFalse(m["business_parity_verified_by_this_audit"])

    def test_trading_release_never_promoted_by_audit(self):
        report = analyze_deep()
        self.assertFalse(report["real_source_authorized"])
        self.assertFalse(report["production_release_approved"])
        self.assertFalse(report["branch_coverage_measured"])

    def test_legacy_sqlite_cache_is_reviewed_not_silently_rewritten(self):
        m = {x["module"]: x for x in analyze_deep()["modules"]}
        self.assertIn("incremental_cache", m)
        self.assertIn("segmented_cache", m)
        self.assertIn("backtest", m)
        self.assertIn("replay", m)
        self.assertGreaterEqual(m["incremental_cache"]["max_function_lines"], 90)
        self.assertEqual(m["incremental_cache"]["provisional_action"], "IMPROVE")
        self.assertGreaterEqual(m["replay"]["consumer_count"], 25)

    def test_output_is_complete_and_deterministic(self):
        a = analyze_deep()
        b = analyze_deep()
        self.assertEqual(a, b)
        rendered = render_matrix(a)
        self.assertEqual(rendered.count("| "), 2 + a["module_count"])
        for item in a["modules"]:
            self.assertIn("| " + item["module"] + " |", rendered)

    def test_nested_function_complexity_counts_individually(self):
        tree = ast.parse(
            "def outer(x):\n"
            "    if x:\n"
            "        return 1\n"
            "    def inner(y):\n"
            "        if y:\n"
            "            return 2\n"
            "        return 3\n"
            "    return inner(x)\n"
        )
        fs = _functions(tree)
        names = {f["name"]: f for f in fs}
        self.assertIn("outer", names)
        self.assertIn("outer.inner", names)
        self.assertEqual(names["outer"]["branch_score"], 2)
        self.assertEqual(names["outer.inner"]["branch_score"], 2)

    def test_bare_exception_detected(self):
        fs = _functions(ast.parse(
            "def unsafe():\n"
            "    try:\n"
            "        1 / 0\n"
            "    except:\n"
            "        pass\n"
        ))
        self.assertEqual(fs[0]["bare_except"], 1)
        self.assertEqual(fs[0]["silent_except"], 1)

    def test_heuristics_not_execution_of_import_time_payload(self):
        with TemporaryDirectory() as tmp:
            package, tests = Path(tmp)/"src", Path(tmp)/"tests"
            package.mkdir()
            tests.mkdir()
            (package/"engineering_contracts.py").write_text("# gate\n", encoding="utf-8")
            marker = Path(tmp)/"executed.txt"
            (package/"example.py").write_text(
                "from pathlib import Path\n"
                + "Path(" + repr(str(marker)) + ").write_text('bad')\n"
                + "def long():\n"
                + "".join("    x = " + str(i) + "\n" for i in range(92))
                + "    return x\n",
                encoding="utf-8",
            )
            report = analyze_deep(package, tests)
            self.assertFalse(marker.exists())
            m = {x["module"]: x for x in report["modules"]}
            self.assertEqual(m["example"]["provisional_action"], "IMPROVE")
            self.assertIn("FUNCTION_90_PLUS", m["example"]["risk_flags"])

    def test_exact_clone_is_review_flag_not_delete_command(self):
        duplicated = "def read_old(x):\n    a = x + 1\n    b = a + 2\n    c = b + 3\n    d = c + 4\n    e = d + 5\n    f = e + 6\n    g = f + 7\n    return g\n"
        tree = ast.parse(duplicated)
        another = ast.parse(duplicated.replace("read_old", "read_new"))
        groups = _duplicates({"old": tree, "new": another})
        self.assertTrue(groups)
        self.assertEqual(len(next(iter(groups.values()))), 2)

    def test_provisional_status_never_claims_replace_remove(self):
        for item in analyze_deep()["modules"]:
            self.assertFalse(item["replacement_authorized"] or item["removal_authorized"])


if __name__ == "__main__":
    unittest.main()
