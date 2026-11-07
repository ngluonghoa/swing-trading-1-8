#!/usr/bin/env python3
"""Complete read-only AST inventory/gate for the Swing Trading Python package.

The audit does NOT run or import provider modules, access networks, evaluate
trading logic, or touch caches. Static analysis is a necessary engineering gate,
not a substitute for integration testing or source qualification.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "swing_trading"
TEST_DIR = ROOT / "tests"
DOMAIN_CORE = frozenset({
    "contracts", "market_data", "causal", "replay", "engine", "backtest",
})
INFRASTRUCTURE = frozenset({
    "d1_mcp_transport_bridge", "dnse_d1_reference_fallback",
    "adaptive_source_router", "incremental_cache", "partition_chunk_cache",
    "segmented_cache", "cache_snapshot_bundle", "fixture_scan",
})
FORBIDDEN_IN_CORE = INFRASTRUCTURE | frozenset({
    "sqlite3", "requests", "httpx", "googleapiclient", "boto3",
})
STORAGE_MODULES = frozenset({
    "cache_fetch_planner", "cache_snapshot_bundle", "fixture_scan",
    "incremental_cache", "partition_chunk_cache", "segmented_cache",
})
SOURCE_MODULES = frozenset({
    "adaptive_source_router", "d1_mcp_transport_bridge",
    "dnse_d1_reference_fallback", "vcbs_source_contract",
    "ssi_source_qualification", "ssi_multivenue_review",
    "ssi_historical_availability", "ssi_intraday_label_diagnostics",
    "ssi_volume_parity", "native_minute_bar_source_plan",
    "c2_source_capability_audit", "c2_fair_source_benchmark",
    "c2_session_probe_readiness",
})
EVIDENCE_MODULES = frozenset({
    "reference_journal", "reference_journal_recovery",
    "reference_offline_verified_archive", "reference_checkpoint_signature",
    "reference_checkpoint_mac", "reference_pinned_fd",
    "reference_storage_preflight", "reference_host_dryrun",
    "evidence_checkpoint", "evidence_recovery", "durable_evidence",
    "provider_head_custody", "provider_signed_event_chain",
    "provider_review_packet", "provider_rights_review",
    "provider_custody_host_plan",
})
RETIRED_C3C = frozenset({
    "drive_c3c_receipt.py", "test_drive_c3c_receipt.py",
})


def owner(module: str) -> str:
    if module in STORAGE_MODULES:
        return "cache_and_persistence"
    if module in SOURCE_MODULES:
        return "source_adapter_and_quality"
    if module in EVIDENCE_MODULES:
        return "evidence_and_rights"
    if module in {"engineering_contracts", "engineering_release", "vn_release_rollback"}:
        return "engineering_governance"
    return "domain_and_reference"


def direct_imports(tree: ast.AST, own_module_names: set[str]) -> tuple[set[str], set[str]]:
    """Imports inside local module, including imports nested inside functions."""
    internal = set()
    external = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:
                if node.module:
                    target = node.module.split(".")[0]
                    internal.add(target)
                else:
                    for alias in node.names:
                        internal.add(alias.name.split(".")[0])
            elif node.level == 0 and node.module:
                parts = node.module.split(".")
                if parts[0] == "swing_trading" and len(parts) > 1:
                    internal.add(parts[1])
                else:
                    external.add(parts[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "swing_trading" and len(parts) > 1:
                    internal.add(parts[1])
                else:
                    external.add(parts[0])
    return internal, external


def cycles(edges: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    visited: set[str] = set()
    active: list[str] = []
    found: set[tuple[str, ...]] = set()

    def visit(module: str) -> None:
        if module in active:
            loop = tuple(active[active.index(module):] + [module])
            found.add(loop)
            return
        if module in visited:
            return
        active.append(module)
        for child in sorted(edges[module]):
            if child in edges:
                visit(child)
        active.pop()
        visited.add(module)

    for module in sorted(edges):
        visit(module)
    return tuple(sorted(found))


def analyze(package_dir: Path = PACKAGE_DIR, test_dir: Path = TEST_DIR) -> dict:
    if not package_dir.is_dir() or not test_dir.is_dir():
        raise ValueError("Explicit source and test directories are required")
    sources = sorted(package_dir.glob("*.py"))
    test_files = sorted(test_dir.glob("test_*.py"))
    names = {p.stem for p in sources}
    deps: dict[str, set[str]] = {}
    modules = []
    violations: list[str] = []
    for file in sources:
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=file.name)
        internal, external = direct_imports(tree, names)
        deps[file.stem] = internal & names
        unresolved = sorted(internal - names)
        if unresolved:
            violations.append("UNRESOLVED_RELATIVE_IMPORT:" + file.stem + ":" + ",".join(unresolved))
        if file.stem in DOMAIN_CORE:
            leak = sorted((internal | external) & FORBIDDEN_IN_CORE)
            if leak:
                violations.append("CORE_IMPORTS_INFRASTRUCTURE:" + file.stem + ":" + ",".join(leak))
        direct = "test_" + file.stem + ".py"
        module_tests = [f.name for f in test_files if f.name == direct]
        modules.append({
            "module": file.stem,
            "owner": owner(file.stem),
            "lines": source.count("\n") + (not source.endswith("\n")),
            "internal_imports": sorted(internal & names),
            "external_imports": sorted(external),
            "direct_test": bool(module_tests),
            "direct_test_files": module_tests,
        })
    for loop in cycles(deps):
        violations.append("IMPORT_CYCLE:" + "->".join(loop))
    for removed in RETIRED_C3C:
        if (package_dir / removed).exists() or (test_dir / removed).exists():
            violations.append("ROLLED_BACK_C3C_REINTRODUCED:" + removed)
    if not any(x["module"] == "engineering_contracts" for x in modules):
        violations.append("MISSING_H1_CONTRACTS")
    uncovered = [x["module"] for x in modules if not x["direct_test"] and x["module"] != "__init__"]
    downstream: dict[str, list[str]] = defaultdict(list)
    for module, imports in deps.items():
        for imported in imports:
            downstream[imported].append(module)
    return {
        "schema": "h2.architecture.inventory.v1",
        "scope": "offline_ast_only_not_runtime_coverage",
        "source_module_count": len(modules),
        "test_file_count": len(test_files),
        "missing_direct_test_modules": uncovered,
        "high_fan_in": [
            {"module": name, "consumer_count": len(importers),
             "consumers": sorted(importers)}
            for name, importers in sorted(downstream.items(),
                                           key=lambda item: (-len(item[1]), item[0]))[:12]
        ],
        "modules": modules,
        "violations": sorted(violations),
        "passes_static_gate": not violations,
        "source_authorized": False,
        "runtime_release_approved": False,
        "backtest_oos_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit nonzero for architecture violations")
    parser.add_argument("--json-out", type=Path, help="Optional evidence output path; never source artifacts")
    args = parser.parse_args(argv)
    report = analyze()
    encoded = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    if args.json_out is not None:
        if not args.json_out.parent.is_dir():
            parser.error("JSON output parent must exist")
        args.json_out.write_text(encoded, encoding="utf-8")
    print(json.dumps({
        "schema": report["schema"],
        "source_module_count": report["source_module_count"],
        "test_file_count": report["test_file_count"],
        "uncovered": report["missing_direct_test_modules"],
        "top_deps": report["high_fan_in"][:7],
        "violations": report["violations"],
        "passes_static_gate": report["passes_static_gate"],
        "real_provider_or_production_qualification": False,
    }, sort_keys=True))
    return int(args.check and bool(report["violations"]))


if __name__ == "__main__":
    sys.exit(main())
