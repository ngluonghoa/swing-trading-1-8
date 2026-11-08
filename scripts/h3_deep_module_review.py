#!/usr/bin/env python3
"""H3: whole-package AST complexity review, never executes provider code.

Classification is PROVISIONAL. Only a separately reviewed PR can actually
approve replacement or removal. A flagged module is not necessarily defective.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from scripts.h2_architecture_audit import analyze, PACKAGE_DIR, TEST_DIR

SCHEMA = "h3.deep-module-review.v1"
_BRANCH = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
           ast.ExceptHandler, ast.Match, ast.Assert)


def _own_nodes(fn):
    stack = list(reversed(list(ast.iter_child_nodes(fn))))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _functions(tree):
    found = []

    def visit(node, parents):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join((*parents, child.name))
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    score = 1
                    silent = bare = 0
                    for part in _own_nodes(child):
                        score += isinstance(part, _BRANCH)
                        if isinstance(part, ast.BoolOp):
                            score += len(part.values) - 1
                        if isinstance(part, ast.comprehension):
                            score += len(part.ifs)
                        if isinstance(part, ast.ExceptHandler):
                            bare += part.type is None
                            if len(part.body) == 1 and isinstance(part.body[0], ast.Pass):
                                silent += 1
                    found.append({
                        "name": qualified, "line": child.lineno,
                        "lines": child.end_lineno - child.lineno + 1,
                        "branch_score": score,
                        "silent_except": silent, "bare_except": bare,
                    })
                visit(child, (*parents, child.name))
            else:
                visit(child, parents)

    visit(tree, ())
    return sorted(found, key=lambda x: (-x["branch_score"], -x["lines"], x["name"]))


def _duplicates(parsed):
    copies = defaultdict(set)
    for name, tree in parsed.items():
        for top in tree.body:
            methods = top.body if isinstance(top, ast.ClassDef) else [top]
            for f in methods:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    f.end_lineno - f.lineno >= 8
                ):
                    norm = ast.dump(ast.Module(body=f.body, type_ignores=[]),
                                    include_attributes=False)
                    copies[norm].add(name + ":" + f.name)
    groups = [sorted(v) for v in copies.values() if len(v) > 1]
    return {"duplicate_" + str(i+1): group for i, group in
            enumerate(sorted(groups, key=lambda v: (-len(v), v)))}


def analyze_deep(package_dir=PACKAGE_DIR, test_dir=TEST_DIR):
    base = analyze(package_dir, test_dir)
    parsed = {file.stem: ast.parse(file.read_text(encoding="utf-8"), filename=file.name)
              for file in sorted(package_dir.glob("*.py"))}
    fanin = Counter(dep for entry in base["modules"]
                    for dep in entry["internal_imports"])
    duplicates = _duplicates(parsed)
    copied = defaultdict(list)
    for k, members in duplicates.items():
        for m in members:
            copied[m.split(":")[0]].append(k)
    modules = []
    for entry in base["modules"]:
        name = entry["module"]
        fs = _functions(parsed[name])
        longest = max((f["lines"] for f in fs), default=0)
        worst = max((f["branch_score"] for f in fs), default=0)
        silent = sum(f["silent_except"] for f in fs)
        bare = sum(f["bare_except"] for f in fs)
        flags = []
        if entry["lines"] >= 500:
            flags.append("FILE_500_PLUS")
        if longest >= 90:
            flags.append("FUNCTION_90_PLUS")
        if worst >= 20:
            flags.append("HIGH_BRANCH_SCORE")
        if fanin[name] >= 10:
            flags.append("HIGH_FAN_IN")
        if silent:
            flags.append("SILENT_EXCEPT")
        if bare:
            flags.append("BARE_EXCEPT")
        if copied[name]:
            flags.append("DUPLICATE_AST")
        # High fan-in alone is not evidence that any refactor is needed.
        candidate = bool(set(flags) - {"HIGH_FAN_IN"})
        modules.append({
            "module": name, "owner": entry["owner"], "lines": entry["lines"],
            "function_count": len(fs),
            "class_count": sum(isinstance(n, ast.ClassDef) for n in parsed[name].body),
            "dependency_count": len(entry["internal_imports"]),
            "consumer_count": fanin[name],
            "statically_imported_by_tests": entry["direct_test_files"],
            "max_function_lines": longest, "max_branch_score": worst,
            "long_or_complex_functions": [f for f in fs
                                         if f["lines"] >= 90 or f["branch_score"] >= 20][:8],
            "silent_except": silent, "bare_except": bare,
            "duplicate_groups": sorted(copied[name]), "risk_flags": flags,
            "provisional_action": "IMPROVE" if candidate else "KEEP",
            "human_review_completed": False,
            "replacement_authorized": False, "removal_authorized": False,
            "business_parity_verified_by_this_audit": False,
        })
    def priority(m):
        weights = {"BARE_EXCEPT": 4, "SILENT_EXCEPT": 4,
                   "HIGH_BRANCH_SCORE": 3, "FUNCTION_90_PLUS": 3,
                   "FILE_500_PLUS": 2, "DUPLICATE_AST": 1,
                   "HIGH_FAN_IN": 1}
        return (-sum(weights[x] for x in m["risk_flags"]),
                -m["consumer_count"], -m["lines"], m["module"])
    ordered = sorted(modules, key=priority)
    return {
        "schema": SCHEMA, "scope": "STATIC_HEURISTIC_NO_PRODUCTION_AUTHORITY",
        "module_count": len(modules),
        "classifications": dict(sorted(Counter(m["provisional_action"]
                                              for m in modules).items())),
        "duplicate_groups": duplicates,
        "priority": [m["module"] for m in ordered],
        "modules": modules,
        "architecture_violations": base["violations"],
        "passes_architecture_gate": base["passes_static_gate"],
        "real_source_authorized": False, "production_release_approved": False,
        "branch_coverage_measured": False,
    }


def render_matrix(report):
    lines = [
        "# H3 — Provisional whole-module review matrix",
        "",
        "This is static prioritization, NOT a human code quality verdict.",
        "KEEP means no threshold breached, NOT error-free. IMPROVE means inspect",
        "before any behavioral refactor. REPLACE and REMOVE are never automatic;",
        "these require separate consumer, migration and rollback evidence.",
        "",
        "| Module | Group | LOC | Max branch | Longest function | Consumers | Proposed | Flags |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for m in report["modules"]:
        lines.append("| " + " | ".join((
            m["module"], m["owner"], str(m["lines"]),
            str(m["max_branch_score"]), str(m["max_function_lines"]),
            str(m["consumer_count"]), m["provisional_action"],
            ", ".join(m["risk_flags"]) or "none",
        )) + " |")
    lines.extend([
        "", "## Review gates",
        "Any proposed change must freeze current fixture behavior, assess direct",
        "and transitive consumers, test corrupt/stale/source-boundary paths,",
        "and demonstrate a scoped rollback. An unchanged module can be kept.",
        "No market provider rights, live cache, release or OOS are certified.", "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--matrix-out", type=Path)
    args = parser.parse_args(argv)
    report = analyze_deep()
    if args.json_out:
        args.json_out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")
    if args.matrix_out:
        args.matrix_out.write_text(render_matrix(report), encoding="utf-8")
    indexed = {m["module"]: m for m in report["modules"]}
    print(json.dumps({
        "schema": report["schema"], "modules": report["module_count"],
        "actions": report["classifications"],
        "top": [{k: indexed[n][k] for k in (
            "module", "risk_flags", "max_function_lines", "max_branch_score",
            "consumer_count")} for n in report["priority"][:14]],
        "duplicate_groups": report["duplicate_groups"],
        "violations": report["architecture_violations"],
    }, sort_keys=True))
    return int(bool(args.check) and (
        not report["passes_architecture_gate"] or
        report["module_count"] < 63
    ))


if __name__ == "__main__":
    sys.exit(main())
