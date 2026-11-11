"""Bind the first C129731 source-shaped CPU construction for offline checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    config = json.loads((HERE / "config.json").read_text())
    case = config["selected_case_id"]
    files = [HERE / name for name in ("runner.py", "finalizer.py", "site_construction.py", "u_turn_control.py",
              "visibility_measure.py", "camera_encoder.py", "camera_setup.py",
              "config.json", "diagnostic-site.json")]
    files += sorted((HERE / "tests").glob("test*.py"))
    entries = [{"path": str(path.relative_to(HERE)), "content": path.read_text(),
                "source": str(path.relative_to(REPO))} for path in files]
    construction = {"case_id": case, "law_id": config["law_id"], "cell_id": config["cell_id"],
                    "actor": config["actor"], "entrypoint": "runner.py", "files": entries,
                    "status": "synthetic_diagnostic_only",
                    "recording_description": config["recording_description"],
                    "measurement_plan": {"sources": ["trace.jsonl", "capture/evidence.jsonl", "motion_history.jsonl",
                                                     "video_frames.jsonl", "overview.mkv", "approach.mkv",
                                                     "reference_corner.mkv", "driver_reference.mkv"],
                                         "saved_finalizer": "finalizer.py"},
                    "static_checks": ["runner --check", "nine package CPU tests"],
                    "termination_rules": ["1100 original frames or explicit failed capture"],
                    "mechanisms": ["reviewed curve/crest geometry required for Native capture",
                                   "spawned static prop with bounding-box verification",
                                   "measured-feedback U-turn and both-direction approach controllers"]}
    target = HERE / "construction.json"
    _dump(target, construction)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": "a4626c89ca4e80fb42351a8fdd4f6aa2601a670a9df51707d306bb45732cdaf3",
                "status": "diagnostic_incomplete", "cases": [{"case_id": case, "kind": "delivery",
                    "construction": target.name, "construction_sha256": _sha(target)}]}
    _dump(HERE / "diagnostic-execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
