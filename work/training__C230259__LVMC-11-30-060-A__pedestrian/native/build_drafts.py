"""Materialize two source-hashed unselected 30-second draft constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = "training__C230259__LVMC-11-30-060-A__pedestrian"
CAMERAS = [{"name": name, "width": width, "height": height} for name, width, height in (
    ("overview", 1920, 1080), ("pedestrian_entry", 1280, 720),
    ("vehicle_approach", 1280, 720), ("roadway_crossing", 1280, 720))]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for n in (1, 2):
        case_id = ASSIGNMENT + f"__probe_{n:02d}"
        description = {"channels": [
            {"name": "pedestrian_footprint", "unit": "m"},
            {"name": "all_roadway_vehicles_pose_speed", "unit": "structured"},
            {"name": "marked_and_unmarked_crosswalk_context", "unit": "survey"},
            {"name": "original_frame_map", "unit": "frame"}],
            "limitations": ["Native capture and actual crosswalk pixels not yet proven",
                            "Section 11.30.070 designated-place prohibition not yet adjudicated"]}
        config = {"case_id": case_id, "selected_case_id": case_id,
                  "supported_case_ids": [case_id], "law_id": "LVMC-11-30-060-A",
                  "cell_id": "C230259", "actor": "pedestrian", "rate_hz": 20,
                  "duration_s": 30, "cameras": CAMERAS, "required_atoms": [],
                  "source_packets": [], "case": {"case_id": case_id},
                  "status": "unselected_native_draft", "recording_description": description}
        files = [
            {"path": "runner.py", "content": (HERE / "draft_runner.py").read_text()},
            {"path": "road.xodr", "content": (HERE / "draft_road.xodr").read_text()},
            {"path": "crossing_meter.py", "content": (HERE / "crossing_meter.py").read_text()},
            {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
            {"path": "tests/test_draft.py", "content": (HERE / "draft_test.py").read_text()},
        ]
        proposal = {"case_id": case_id, "law_id": "LVMC-11-30-060-A",
                    "cell_id": "C230259", "actor": "pedestrian", "entrypoint": "runner.py",
                    "files": files, "recording_description": description,
                    "status": "selected_cpu_draft_physical_unverified" if n == 2 else "comparison_cpu_draft"}
        output = ROOT / f"draft-probe-{n:02d}"
        output.mkdir(exist_ok=True)
        construction = output / "construction.json"
        construction.write_text(json.dumps(proposal, indent=2) + "\n")
        entries.append({"case_id": case_id, "id": "primary", "kind": "delivery" if n == 2 else "comparison_draft",
                        "construction": str(construction.relative_to(ROOT)),
                        "construction_sha256": sha(construction),
                        "candidate_risk": {"status": "physical",
                                           "reason": "Native crossing route and visible source pixels are unverified"},
                        "candidates": []})
    manifest = {"format": "worker-selected-cpu-draft-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "partial", "cases": entries}
    (ROOT / "draft-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(entries), "manifest_sha256": sha(ROOT / "draft-manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
