"""Construct five exact source-gated controlled-access bundles for offline proof."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, ACTOR, CAMERAS, CELL, LAW, RECORDING

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ("analysis.py", "access_probe.py", "access.py", "access_capture.py",
           "access_capture_audit.py", "access_carla_adapter.py", "package_spec.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("exact construction exceeds 2 MiB")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if (plan["assignment_id"], plan["law_id"], plan["cell_id"], plan["actor"]) != (AID, LAW, CELL, ACTOR):
        raise ValueError("controlled-access case-plan identity differs")
    ids = [case["case_id"] for case in plan["cases"]]
    if len(ids) != 5 or len(set(ids)) != 5:
        raise ValueError("five distinct exact cases required")
    entries = []
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        config = {"assignment_id": AID, "law_id": LAW, "cell_id": CELL,
                  "actor": ACTOR, "selected_case_id": case["case_id"],
                  "candidate_id": "primary", "rate_hz": 20, "duration_s": 45,
                  "required_atoms": [], "source_packets": [],
                  "cameras": CAMERAS, "supported_case_ids": ids,
                  "case": {**case, "recording_description": RECORDING}}
        files = [{"path": "runner.py", "content": (HERE / "original_runner.py").read_text()},
                 {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                 {"path": "tests/test_bundle.py", "content": (HERE / "bundle_test.py").read_text()}]
        files += [{"path": name, "content": (HERE / name).read_text()} for name in SOURCES]
        construction = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                        "case_id": case["case_id"], "entrypoint": "runner.py",
                        "recording_description": RECORDING, "files": files}
        path = HERE / ("construction-selected-" + suffix + ".json")
        write(path, construction)
        entries.append({"case_id": case["case_id"], "kind": "delivery",
                        "construction": path.name, "construction_sha256": sha(path),
                        "candidate_risk": {"status": "physical",
                                           "reason": "The Native vehicle may leave the designated boundary crossing or fail to show erected official notice, and original video may miss the device placement; a reviewed steering-gain fallback is reserved."},
                        "candidates": []})
    write(HERE / "execution-manifest.selected-draft.json",
          {"format": "worker-execution-manifest", "assignment_id": AID,
           "status": "selected_bundle_proofs_pending",
           "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
           "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print("selected exact controlled-access drafts:", build())
