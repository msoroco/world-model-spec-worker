"""Review both original sources in one exact accepted-reuse comparison.

This is a scratch-only source and geometry review, not canonical acceptance or
a determination that another driver could see the turning vehicle.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from original_source_acquisition import acquire
from selected_media_audit import audit_acquired, audit_selected_pair


def run(plan: dict, repository: Path, comparison_id: str, attempts: tuple[Path, Path],
        bundles: tuple[Path, Path], output: Path) -> dict:
    worker_root = Path(__file__).resolve().parents[2]
    scratch = worker_root / ".runtime-work"
    if len(attempts) != 2 or len(bundles) != 2:
        raise ValueError("two exact comparison sides required")
    if bundles[0].resolve() == bundles[1].resolve():
        raise ValueError("comparison source bundles must be distinct")
    for path in (*bundles, output):
        if not Path(path).resolve().is_relative_to(scratch):
            raise ValueError("comparison outputs must be under .runtime-work")
        if Path(path).exists():
            raise ValueError("refusing to overwrite comparison output")
    pairs = [row for row in plan.get("accepted_comparisons_pending_original_review", [])
             if row.get("comparison_id") == comparison_id]
    if len(pairs) != 1:
        raise ValueError("unknown or duplicated accepted comparison")
    pair = pairs[0]
    inventories = [json.loads((Path(attempt) / "inventory.json").read_text())
                   for attempt in attempts]
    if ([row.get("case_id") for row in inventories] != pair.get("case_ids") or
            [row.get("recording_id") for row in inventories] != pair.get("recording_ids")):
        raise ValueError("selected pair sight-attempt identity mismatch")
    for i in range(2):
        acquire(plan, repository, pair["case_ids"][i], pair["recording_ids"][i], bundles[i])
    selected = [audit_acquired(plan, repository, attempts[i], bundles[i]) for i in range(2)]
    joined = audit_selected_pair(
        plan, repository, comparison_id,
        (attempts[0], bundles[0] / "raw.mkv", bundles[0] / "trace.json"),
        (attempts[1], bundles[1] / "raw.mkv", bundles[1] / "trace.json"))
    if [row["metadata_sha256"] for row in joined["selected_media"]] != [
            row["metadata_sha256"] for row in selected]:
        raise ValueError("selected pair source review changed after acquisition")
    result = {"format": "c129731-selected-original-pair-review-v1",
              "comparison_id": comparison_id,
              "case_ids": pair["case_ids"], "recording_ids": pair["recording_ids"],
              "source_reviews": selected, "comparison": joined["comparison"],
              "law_specific_visibility_review": "unresolved",
              "canonical_acceptance": "not_performed_here"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--left-bundle", type=Path, required=True)
    parser.add_argument("--right-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(json.loads(args.plan.read_text()), args.repository, args.comparison,
        (args.left_attempt, args.right_attempt), (args.left_bundle, args.right_bundle),
        args.output)


if __name__ == "__main__":
    main()
