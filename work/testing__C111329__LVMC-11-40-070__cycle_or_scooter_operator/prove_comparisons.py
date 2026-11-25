"""Run source-hashed diagnostic comparison positives and missing-source negatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from comparison_audit import audit_from_sources

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def run_one(comparison_id: str, negative: bool) -> dict:
    comparison = next(row for row in PLAN["comparisons"] if row["comparison_id"] == comparison_id)
    cases = {row["case_id"]: row for row in PLAN["cases"]}
    first = comparison["case_ids"][0].split("__")[-1]
    site = ROOT / "cases" / first / "diagnostic-site.json"
    traces = {case_id: (ROOT / "cases" / case_id.split("__")[-1] /
                        "diagnostic-instruction-trace.json") for case_id in comparison["case_ids"]}
    if negative:
        site = ROOT / "cases" / first / "missing-site.json"
    receipt = audit_from_sources(comparison, cases, site,
                                 sha(site) if site.exists() else "0" * 64,
                                 {case_id: (path, sha(path)) for case_id, path in traces.items()},
                                 diagnostic=True)
    receipt["source_kind"] = "synthetic_fixture_comparison"
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.comparison_id:
        print(json.dumps(run_one(args.comparison_id, args.negative), sort_keys=True))
        return
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    proofs = []
    for comparison in PLAN["comparisons"]:
        ident = comparison["comparison_id"]
        suffix = ident.split("__")[-1]
        commands = []
        logs = []
        for negative in (False, True):
            command = [sys.executable, str((ROOT / "prove_comparisons.py").relative_to(REPO)),
                       "--comparison-id", ident] + (["--negative"] if negative else [])
            completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log = ROOT / f"comparison-{suffix}-{'negative' if negative else 'positive'}.log"
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n")
            if negative and (completed.returncode == 0 or "missing-site.json" not in log.read_text()):
                raise ValueError("missing comparison source did not fail")
            if not negative and (completed.returncode != 0 or not json.loads(completed.stdout)["passed"]):
                raise ValueError("diagnostic comparison did not pass: " + log.read_text())
            commands.append(" ".join(command))
            logs.append((log.name, sha(log), completed.returncode))
        proofs.append({"comparison_id": ident, "diagnostic_fixture": True,
                       "physical_acceptance": False, "positive_command": commands[0],
                       "positive_log": logs[0][0], "positive_log_sha256": logs[0][1],
                       "positive_exit_code": logs[0][2], "negative_command": commands[1],
                       "negative_log": logs[1][0], "negative_log_sha256": logs[1][1],
                       "negative_exit_code": logs[1][2],
                       "negative_expected_error": "missing-site.json"})
        print("passed", suffix)
    manifest["comparison_audits"] = proofs
    dump(manifest_path, manifest)


if __name__ == "__main__":
    main()
