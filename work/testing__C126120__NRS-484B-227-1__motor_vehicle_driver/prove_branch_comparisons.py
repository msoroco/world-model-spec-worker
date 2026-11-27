"""Prove the three additional controlled comparisons on textual CPU diagnostics."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from branch_comparison_audit import PAIRS, audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def packet(suffix):
    diagnostic = json.loads((HERE / "cases" / suffix / "diagnostic.json").read_text())
    files = diagnostic["files"]
    return {"context": json.loads(files["median-context.json"]),
            "samples": [json.loads(line) for line in
                        files["ego-body-history.jsonl"].splitlines()],
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}


def main():
    for comparison_id, (left, right) in PAIRS.items():
        sources = {}
        for suffix in (left, right):
            source = HERE / "cases" / suffix / "comparison-source.json"
            write(source, packet(suffix))
            config = (HERE / "config.json" if suffix == "opening_single"
                      else HERE / "cases" / suffix / "config.json")
            sources[suffix] = (source, sha(source), config, sha(config))
        lp, lh, lc, lch = sources[left]
        rp, rh, rc, rch = sources[right]
        result = audit(comparison_id, lp, lh, rp, rh, lc, lch, rc, rch)
        if result["legal_verdict_claimed"]:
            raise AssertionError("branch audit claimed legal verdict")
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                         prefix="c126120-branch-") as temporary:
            changed = Path(temporary) / "changed.json"
            changed.write_text(lp.read_text() + " ")
            try:
                audit(comparison_id, changed, lh, rp, rh, lc, lch, rc, rch)
            except ValueError as exc:
                if "original source hash mismatch" not in str(exc):
                    raise
            else:
                raise AssertionError("changed original source accepted")
            changed_packet = copy.deepcopy(packet(right))
            changed_packet["context"]["source_right_roadway_id"] = "wrong-source-roadway"
            write(changed, changed_packet)
            try:
                audit(comparison_id, lp, lh, changed, sha(changed), lc, lch, rc, rch)
            except ValueError as exc:
                if "fixed" not in str(exc):
                    raise
            else:
                raise AssertionError("changed fixed source accepted")
        receipt = {
            "comparison_id": comparison_id,
            "case_ids": result["case_ids"],
            "declared_differences": result["declared_differences"],
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "sources": {left: {"path": str(lp.relative_to(HERE)), "sha256": lh},
                        right: {"path": str(rp.relative_to(HERE)), "sha256": rh}},
            "measured_difference_test_passed": True,
            "changed_original_rejected": True,
            "changed_fixed_source_rejected": True,
            "actual_native_pair_claimed": False,
        }
        write(HERE / "comparisons" / (comparison_id + ".json"), receipt)
        print(comparison_id, "diagnostic difference and negative source checks passed")


if __name__ == "__main__":
    main()
