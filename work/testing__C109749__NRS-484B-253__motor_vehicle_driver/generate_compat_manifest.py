"""Generate a draft one-case runtime compatibility manifest, never a ready claim."""

import hashlib
import json
from pathlib import Path

from generate_bundles import RECORDING_DESCRIPTION
from construction import POLICIES
from requirement_finalizer import ASSIGNMENT_ID

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def generate():
    entries = []
    for suffix in POLICIES:
        construction = ROOT / "cases" / suffix / "construction.json"
        entry = {"case_id": ASSIGNMENT_ID + "__" + suffix,
                 "kind": "diagnostic_compatibility_checkpoint",
                 "construction": "cases/" + suffix + "/construction.json",
                 "construction_sha256": sha(construction),
                 "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                 "measurement_procedure": {"entrypoint": "analysis.py"},
                 "fixture_recipe": str((ROOT / "cases" / suffix / "fixture-recipe.json").relative_to(ROOT.parents[1])),
                 "candidate_risk": {"status": "physical", "reason": "Unreviewed junction route may miss the physical turn."},
                 "acquisition": {name: {"entrypoint": "native_acquisition.py",
                                        "method": "original 20 Hz actor sample",
                                        "evidence": "original-trace.jsonl"}
                                 for name in ("ego_body_history", "opponent_body_history",
                                              "ego_signal_history")}}
        receipt = ROOT / "cases" / suffix / "compatibility.json"
        if receipt.is_file():
            proof = json.loads(receipt.read_text(encoding="utf-8"))
            if (proof.get("case_id") != entry["case_id"] or
                    proof.get("construction_sha256") != entry["construction_sha256"] or
                    proof.get("passed") is not True):
                raise ValueError("stale exact compatibility receipt: " + suffix)
            entry["compatibility"] = {"receipt": "cases/" + suffix + "/compatibility.json",
                "sha256": sha(receipt), "log": "cases/" + suffix + "/compat-analysis.log",
                "command_log": "cases/" + suffix + "/compat-command.log",
                "command_log_sha256": sha(ROOT / "cases" / suffix / "compat-command.log"),
                "exit_code": 0}
            entry["negative"] = {"log": "cases/" + suffix + "/compat-negative.log"}
        fallback = ROOT / "cases" / suffix / "fallback1-construction.json"
        if fallback.is_file():
            entry["candidate_risk"] = {"status": "physical",
                "reason": "Two opposing bodies may collide or miss the intended temporal sequence."}
            entry["candidates"] = [{"id": "fallback1",
                "construction": "cases/" + suffix + "/fallback1-construction.json",
                "construction_sha256": sha(fallback),
                "trigger": {"source": "original Native actor trace and contact events",
                            "metric": "ego physical clearance and actor contact before frame 900",
                            "failure_condition": "ego did not clear reviewed intersection or any participant contact occurred"},
                "changed_knobs": ["ego controller target_speed_mps: 5.0 to 3.0"]}]
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT_ID,
                "runtime_manifest_sha256": sha(ROOT.parents[1] / "runtime/SOURCE-MANIFEST.json"),
                "status": "draft_compatibility_pending", "cases": entries}
    write(ROOT / "execution-manifest.json", manifest)


if __name__ == "__main__":
    generate()
    print("draft exact-case compatibility manifest generated")
