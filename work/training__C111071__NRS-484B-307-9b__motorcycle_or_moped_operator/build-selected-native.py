"""Bind current C111071 Native sources into four exact selected CPU bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = ("probe_1", "probe_2", "yield_wait_for_clearance",
         "yield_enter_during_occupancy")
SOURCES = ("runner.py", "cycle_controller.py", "saved_measurement.py",
           "finalize.py", "live_capture.py", "source_bridge.py",
           "authored-road.xodr")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries = []
    for suffix in CASES:
        draft = json.loads((HERE / f"draft-{suffix.replace('_', '-')}/construction.json").read_text())
        case_id = draft["case_id"]
        config = next(json.loads(item["content"]) for item in draft["files"]
                      if item["path"] == "config.json")
        config["status"] = "selected_delivery_cpu_in_progress"
        files = [{"path": name, "source": str((HERE / "native" / name).relative_to(REPO)),
                  "content": (HERE / "native" / name).read_text()}
                 for name in SOURCES]
        files.extend(({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      next(item for item in draft["files"]
                           if item["path"] == "tests/test_draft.py")))
        construction = {key: draft[key] for key in (
            "case_id", "law_id", "cell_id", "actor", "recording_description")}
        construction.update({"entrypoint": "runner.py", "files": files,
                             "status": "selected_delivery_cpu_in_progress"})
        target = HERE / "selected-native" / suffix / "construction.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": case_id, "kind": "delivery", "id": "primary",
                        "construction": str(target.relative_to(HERE)),
                        "construction_sha256": sha(target),
                        "fixture_recipe": str((HERE / f"current-v2-{suffix.replace('_', '-')}-fixture-recipe.json").relative_to(REPO)),
                        "measurement_contract": f"current-v2-{suffix.replace('_', '-')}-measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "finalize.py",
                                                  "output_schema": "c111071-saved-finalizer-report-v1"},
                        "candidate_risk": {"status": "physical",
                                           "reason": "Original stop, two-cycle timing and conflict occupancy may fail in the imported Native world"},
                        "candidates": [],
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT"}})
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": HERE.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "selected_delivery_cpu_in_progress",
                "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": len(entries), "manifest_sha256": sha(HERE / "execution-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
