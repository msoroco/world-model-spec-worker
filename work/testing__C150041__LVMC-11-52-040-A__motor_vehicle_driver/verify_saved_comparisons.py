"""Run four measured comparison audits on source-specific synthetic fixtures."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from parking_comparison_audit import PAIRS, audit
from parking_finalizer import finalize
from parking_pose import REQUESTS


REPO = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(prefix):
    prefix = str(prefix)
    results = {}
    fixtures = {}
    scratch = (REPO / ".runtime-work").resolve()
    for kind in REQUESTS:
        fixture = Path(prefix + kind).resolve()
        if not fixture.is_dir() or not fixture.is_relative_to(scratch):
            raise ValueError("all six synthetic fixtures must be under .runtime-work")
        packet = fixture / "reviewed-context.json"
        history = fixture / "parking-history.jsonl"
        results[kind] = finalize(packet, fixture, kind, history, sha(history))
        fixtures[kind] = {"packet_sha256": sha(packet), "history_sha256": sha(history)}
    comparisons = {name: audit(results[left], results[right], name)
                   for name, (left, right, _) in PAIRS.items()}
    changed = copy.deepcopy(results["park_angled_lawful"])
    changed["source_packet_sha256"] = "0" * 64
    try:
        audit(results["park_parallel_lawful"], changed, "park_parallelism")
    except ValueError as exc:
        if "source packet differs" not in str(exc):
            raise
        changed_packet_rejection = str(exc)
    else:
        raise ValueError("changed comparison source packet passed")
    changed = copy.deepcopy(results["park_angled_lawful"])
    same = results["park_parallel_lawful"]["observations"][-1]
    changed["observations"][-1]["lawful_heading_deviation_deg"] = same["lawful_heading_deviation_deg"]
    changed["observations"][-1]["parallel_deviation_deg"] = same["parallel_deviation_deg"]
    try:
        audit(results["park_parallel_lawful"], changed, "park_parallelism")
    except ValueError as exc:
        if "measured orientation difference" not in str(exc):
            raise
        missing_difference_rejection = str(exc)
    else:
        raise ValueError("comparison with no measured difference passed")
    return {"format": "c150041-synthetic-comparison-fixture-proof", "passed": True,
            "diagnostic_only": True, "fixtures": fixtures, "comparisons": comparisons,
            "changed_packet_rejection": changed_packet_rejection,
            "missing_difference_rejection": missing_difference_rejection,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-prefix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    proof = verify(args.fixture_prefix)
    Path(args.output).write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparisons": list(proof["comparisons"]),
                      "diagnostic_only": True}))
