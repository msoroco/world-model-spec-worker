"""Run three exact diagnostic source pairs through the independent audit."""
from __future__ import annotations

import hashlib
import json
import shlex
import tempfile
from pathlib import Path

from comparison_audit import PAIRS, audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    cases = {entry["case_id"].rsplit("__",1)[-1]:entry for entry in manifest["cases"]}
    originals = {}
    for suffix in sorted({item for left,right,_ in PAIRS.values() for item in (left,right)}):
        entry = cases[suffix]
        tokens = shlex.split(entry["compatibility"]["command"])
        output = Path(tokens[tokens.index("--output")+1])
        packet = {"context": json.loads((output / "median-context.json").read_text()),
                  "samples": [json.loads(line) for line in (output / "ego-body-history.jsonl").read_text().splitlines()],
                  "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}
        path = HERE / "cases" / suffix / "comparison-source.json"
        write(path, packet)
        config = HERE / "config.json" if suffix == "opening_single" else HERE / "cases" / suffix / "config.json"
        originals[suffix] = (path, sha(path), config, sha(config))
    receipts = []
    for comparison_id,(left,right,_) in PAIRS.items():
        args = (*originals[left], *originals[right])
        # Reorder source/config pairs for the audit's explicit signature.
        lp,lh,lc,lch = originals[left]
        rp,rh,rc,rch = originals[right]
        result = audit(comparison_id,lp,lh,rp,rh,lc,lch,rc,rch)
        if result["legal_verdict_claimed"] or result["case_ids"] != [cases[left]["case_id"],cases[right]["case_id"]]:
            raise AssertionError("comparison identity or judgment scope changed")
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",prefix="c126120-comparison-") as tmp:
            altered = Path(tmp) / "changed.json"
            altered.write_text(lp.read_text() + " ")
            try:
                audit(comparison_id,altered,lh,rp,rh,lc,lch,rc,rch)
            except ValueError as exc:
                if "comparison original source hash mismatch" not in str(exc):
                    raise
            else:
                raise AssertionError("changed original pair source accepted")
        receipt = {"comparison_id":comparison_id,"provenance_kind":"synthetic_fixture",
                   "diagnostic_fixture":True,"case_ids":result["case_ids"],
                   "sources":{left:{"path":str(lp.relative_to(HERE)),"sha256":lh},
                              right:{"path":str(rp.relative_to(HERE)),"sha256":rh}},
                   "declared_differences":result["declared_differences"],
                   "measured_difference_test_passed":True,"changed_original_rejected":True,
                   "actual_native_pair_claimed":False}
        target = HERE / "comparisons" / (comparison_id + ".json")
        target.parent.mkdir(exist_ok=True)
        write(target,receipt)
        receipts.append(str(target.relative_to(HERE)))
        print(comparison_id,"diagnostic pair and changed-source rejection passed")
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for item in plan["comparisons"]:
        if item["comparison_id"] in PAIRS:
            item["status"] = "diagnostic_pair_audit_passed_original_native_pair_pending"
            item["cpu_proof"] = "comparisons/" + item["comparison_id"] + ".json"
    write(plan_path,plan)


if __name__ == "__main__":
    main()
