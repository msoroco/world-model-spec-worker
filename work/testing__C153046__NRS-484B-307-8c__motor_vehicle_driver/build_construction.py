"""Build source-hashed, case-specific CPU construction proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_case_plan import AID, KINDS

ROOT = Path(__file__).resolve().parent
SOURCES = ["runner.py", "native_runner.py", "native_frame.py", "red_left_turn_controller.py",
           "source_bound_scene.py", "build_case_plan.py", "case-plan.json",
           "tests/__init__.py", "tests/test_case_plan.py",
           "tests/test_red_left_turn_controller.py", "tests/test_source_bound_scene.py",
           "tests/test_native_runner.py", "tests/test_native_frame.py"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    cases = []
    folder = ROOT / "constructions"
    folder.mkdir(exist_ok=True)
    for suffix, variables in KINDS.items():
        case_id = AID + "__" + suffix
        config = {"assignment_id": AID, "selected_case_id": case_id,
                  "law_id": "NRS-484B-307-8c", "cell_id": "C153046",
                  "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
                  "capture_provenance": "original Native samples required",
                  "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id, "draft_variables": variables},
                  "physical_completion": {"criterion": "original stop, entry, yield, and exit histories",
                                          "status": "unverified"}}
        files = [{"path": name, "content": (ROOT / name).read_text()} for name in SOURCES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {"case_id": case_id, "cell_id": "C153046",
                        "law_id": "NRS-484B-307-8c", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": "Original one-way-left red-alone controlled attempt: " + suffix,
                        "mechanisms": ["source-bound site geometry and live OpenDRIVE byte match",
                                       "Native world tick, signal and full participant body acquisition",
                                       "CARLA-lazy actor control application and text trace"],
                        "status": "partial: CPU protocol; reviewed site and physical proof pending"}
        path = folder / (suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        cases.append({"case_id": case_id, "kind": "delivery",
                      "construction": str(path.relative_to(ROOT)),
                      "construction_sha256": digest(path),
                      "candidate_risk": {"status": "unverified",
                                         "reason": "No reviewed site geometry yet; a concrete physical fallback trigger cannot be selected."},
                      "proof_status": "offline_pending_physical_and_compatibility"})
    manifest = {"assignment_id": AID, "law_id": "NRS-484B-307-8c",
                "cell_id": "C153046", "actor": "motor_vehicle_driver", "cases": cases,
                "status": "partial draft; no Native source, recording or delivery acceptance"}
    (ROOT / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print("built", len(build()["cases"]), "exact construction proposals")
