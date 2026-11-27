"""Source-bound continuous versus multiple movement comparison and rejection."""
from __future__ import annotations

import hashlib
import json
import shlex
import tempfile
from pathlib import Path

from comparison_audit import audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAIR = "continuous_vs_multiple_movement"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    originals = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        tokens = shlex.split(entry["compatibility"]["command"])
        output = Path(tokens[tokens.index("--output")+1])
        packet = {"context":json.loads((output/"median-context.json").read_text()),
                  "samples":[json.loads(line) for line in (output/"ego-body-history.jsonl").read_text().splitlines()],
                  "provenance_kind":"synthetic_fixture", "diagnostic_fixture":True}
        target = HERE/"cases"/suffix/"comparison-source.json"
        target.write_text(json.dumps(packet,indent=2,sort_keys=True)+"\n")
        config = HERE/"config.json" if suffix == "opening_single" else HERE/"cases"/suffix/"config.json"
        originals[suffix]=(target,sha(target),config,sha(config))
    lp,lh,lc,lch=originals["opening_single"]
    rp,rh,rc,rch=originals["opening_multiple"]
    measured = audit(PAIR,lp,lh,rp,rh,lc,lch,rc,rch)
    if measured["legal_verdict_claimed"] or measured["case_ids"] != [e["case_id"] for e in manifest["cases"]]:
        raise AssertionError("exact pair identity changed")
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c80909-comparison-") as scratch:
        changed = Path(scratch)/"changed.json"
        changed.write_text(lp.read_text()+" ")
        try:
            audit(PAIR,changed,lh,rp,rh,lc,lch,rc,rch)
        except ValueError as exc:
            if "comparison original source hash mismatch" not in str(exc): raise
        else:
            raise AssertionError("changed original comparison source accepted")
        changed_config = Path(scratch)/"changed-config.json"
        config = json.loads(rc.read_text())
        config["case"]["observed_vehicle"]["position_xy_m"][0] += 1.0
        changed_config.write_text(json.dumps(config,sort_keys=True)+"\n")
        try:
            audit(PAIR,lp,lh,rp,rh,lc,lch,changed_config,sha(changed_config))
        except ValueError as exc:
            if "fixed comparison context changed: observed_vehicle" not in str(exc): raise
        else:
            raise AssertionError("changed fixed other vehicle accepted")
    receipt={"comparison_id":PAIR,"case_ids":measured["case_ids"],
             "provenance_kind":"synthetic_fixture","diagnostic_fixture":True,
             "sources":{"opening_single":{"path":str(lp.relative_to(HERE)),"sha256":lh},
                        "opening_multiple":{"path":str(rp.relative_to(HERE)),"sha256":rh}},
             "declared_differences":measured["declared_differences"],
             "measured_difference_test_passed":True,"changed_original_rejected":True,
             "changed_fixed_context_rejected":True,
             "actual_native_pair_claimed":False}
    target=HERE/"comparisons"/(PAIR+".json");target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print(PAIR,"positive and changed-source negative checks passed")


if __name__=="__main__": main()
