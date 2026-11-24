"""Replay five diagnostic exact-case comparisons from source-shaped text.

This is a software source-join proof. Later reciprocal actor identity and legal
right-of-way remain unresolved without original Native actor records.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from comparison_audit import audit
from construction import POLICIES
from saved_left_turn import ASSIGNMENT_ID, process

ROOT = Path(__file__).resolve().parent
NAMES = ("original-map.json", "original-trace.jsonl", "acquisition-receipt.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(output_root):
    output_root = Path(output_root)
    if output_root.exists():
        raise ValueError("Use a fresh ignored comparison output directory")
    output_root.mkdir(parents=True)
    measured = {}
    bindings = {}
    for suffix in POLICIES:
        source = json.loads((ROOT / "cases" / suffix / "diagnostic.json").read_text(encoding="utf-8"))
        folder = output_root / suffix
        folder.mkdir()
        for name in NAMES:
            (folder / name).write_text(source["files"][name], encoding="utf-8")
        case_id = ASSIGNMENT_ID + "__" + suffix
        measured[case_id] = process(case_id=case_id, map_path=folder / NAMES[0],
                                    trace_path=folder / NAMES[1],
                                    receipt_path=folder / NAMES[2],
                                    allow_diagnostic=True)
        bindings[case_id] = {name: sha(folder / name) for name in NAMES}
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    positives = []
    for pair in plan["comparisons"]:
        left, right = (measured[case_id] for case_id in pair["case_ids"])
        receipt = audit(plan_path=plan_path, comparison_id=pair["comparison_id"],
                        left=left, right=right)
        receipt["source_sha256"] = {case_id: bindings[case_id] for case_id in pair["case_ids"]}
        receipt["scope"] = "synthetic diagnostic software comparison only"
        positives.append(receipt)
    negatives = []
    pair = plan["comparisons"][0]
    left, right = (measured[case_id] for case_id in pair["case_ids"])
    for label, mutation, error in (
        ("identical_observed_response", lambda r: r.update(frames=copy.deepcopy(left["frames"])),
         "declared measured difference absent"),
        ("same_acquisition", lambda r: r.update(source_id=left["source_id"]),
         "comparison needs distinct original sources"),
        ("different_map", lambda r: r.update(map_sha256="b" * 64),
         "comparison Native map differs"),
    ):
        changed = copy.deepcopy(right)
        mutation(changed)
        try:
            audit(plan_path=plan_path, comparison_id=pair["comparison_id"],
                  left=left, right=changed)
        except ValueError as failure:
            if error not in str(failure):
                raise
            negatives.append({"probe": label, "expected_error": error,
                              "observed_error": str(failure)})
        else:
            raise ValueError("Negative comparison did not reject: " + label)
    return {"format": "worker-diagnostic-comparison-proof",
            "assignment_id": ASSIGNMENT_ID, "case_plan_sha256": sha(plan_path),
            "passed": True, "positive_count": len(positives),
            "negative_count": len(negatives), "positives": positives,
            "negatives": negatives, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False,
            "limitations": ["Actual Native body, signal and pixels are not established.",
                            "Later reciprocal opponent identity is unresolved."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    value = prove(args.output_root)
    Path(args.receipt).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"positive_count": value["positive_count"],
                      "negative_count": value["negative_count"], "passed": True}))


if __name__ == "__main__":
    main()
