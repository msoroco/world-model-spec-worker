"""Build all exact original-source case bundles for pinned offline checks."""

import hashlib
import json
from pathlib import Path

from package_spec import ACTOR, AID, CAMERAS, CELL, LAW, RECORDING


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ("original_runner.py", "analysis.py", "pass_native_capture.py", "pass_scene.py",
           "pass_controller.py", "pass_measurements.py", "package_spec.py",
           "pass_capture_audit.py")


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned exact construction exceeds 2 MiB")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    if (plan["assignment_id"], plan["law_id"], plan["cell_id"], plan["actor"]) != (AID, LAW, CELL, ACTOR):
        raise ValueError("exact case plan scope changed")
    ids = [case["case_id"] for case in plan["cases"]]
    if len(ids) != 14 or len(set(ids)) != 14:
        raise ValueError("all fourteen exact branches required")
    entries = []
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                  "selected_case_id": case["case_id"], "candidate_id": "primary",
                  "rate_hz": 20, "duration_s": 45, "required_atoms": [],
                  "source_packets": [], "cameras": CAMERAS,
                  "supported_case_ids": ids,
                  "case": {**case, "recording_description": RECORDING}}
        files = [{"path": "runner.py", "content": (HERE / "original_runner.py").read_text()},
                 {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                 {"path": "tests/test_bundle.py", "content": (HERE / "bundle_test.py").read_text()}]
        files += [{"path": name, "content": (HERE / name).read_text()} for name in SOURCES if name != "original_runner.py"]
        construction = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                        "case_id": case["case_id"], "entrypoint": "runner.py",
                        "recording_description": RECORDING, "files": files}
        path = HERE / ("construction-selected-" + suffix + ".json")
        write(path, construction)
        entries.append({"case_id": case["case_id"], "kind": "delivery",
                        "construction": path.name, "construction_sha256": sha(path),
                        "candidate_risk": {"status": "physical",
                                           "reason": "Native rider overtaking, lane entry and four-camera framing can miss the planned route; candidate policy and source proof remain to be authored."},
                        "candidates": []})
    write(HERE / "execution-manifest.selected-draft.json",
          {"format": "worker-execution-manifest", "assignment_id": AID,
           "status": "selected_bundle_offline_proofs_pending",
           "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
           "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print("built exact selected drafts:", build())
