"""Independently compare ready primary and fallback construction contracts.

This static review identifies contract drift for human follow-up. It does not
establish physical suitability or replace case-specific CPU proofs.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def preserved(primary: object, fallback: object) -> bool:
    if primary == fallback:
        return True
    if isinstance(primary, str) and isinstance(fallback, str):
        return fallback.startswith(primary)
    if isinstance(primary, dict) and isinstance(fallback, dict):
        return all(key in fallback and preserved(value, fallback[key])
                   for key, value in primary.items())
    if isinstance(primary, list) and isinstance(fallback, list):
        return all(value in fallback for value in primary)
    return False


def audit(repo: Path) -> dict:
    cases = 0
    candidates = 0
    anomalies = []
    changed = Counter()
    for result in sorted((repo / "work").glob("*/result.json")):
        if read(result).get("status") != "ready":
            continue
        folder = result.parent
        manifest = folder / "execution-manifest.json"
        if not manifest.is_file():
            continue
        for case in read(manifest).get("cases", []):
            cases += 1
            primary_path = folder / case["construction"]
            primary = read(primary_path)
            for candidate in case.get("candidates", []):
                candidates += 1
                fallback = read(folder / candidate["construction"])
                identity = {key: primary.get(key) for key in
                            ("law_id", "cell_id", "actor", "case_id", "entrypoint")}
                changed_keys = sorted(key for key in set(primary) | set(fallback)
                                      if key != "files" and primary.get(key) != fallback.get(key))
                changed.update(changed_keys)
                problems = []
                if any(fallback.get(key) != value for key, value in identity.items()):
                    problems.append("identity_drift")
                for key in ("recording_description", "measurement_plan",
                            "termination_rules", "static_checks"):
                    if key in primary and not preserved(primary[key], fallback.get(key)):
                        problems.append(key + "_not_preserved")
                if problems:
                    anomalies.append({"assignment_id": folder.name,
                                      "case_id": case["case_id"],
                                      "candidate_id": candidate.get("id"),
                                      "problems": problems,
                                      "changed_nonfile_keys": changed_keys})
    return {"format": "worker-candidate-differential-audit",
            "ready_cases_checked": cases, "candidates_checked": candidates,
            "changed_nonfile_keys": dict(sorted(changed.items())),
            "anomalies": anomalies,
            "finding": "Static primary/fallback contract preservation only; original Native behavior and comparison isolation need case-specific review."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
