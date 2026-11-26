"""Materialize canonical assignment entrypoint and exact camera plan."""

import json
import shutil
from pathlib import Path


folder = Path(__file__).resolve().parents[1]
native = folder / "native"
manifest = json.loads((folder / "execution-manifest.json").read_text())
primary = json.loads((folder / manifest["cases"][0]["construction"]).read_text())
for name in ("runner.py", "controller.py", "door_actuation.py",
             "measure_door.py", "finalize.py"):
    shutil.copyfile(native / name, folder / name)
test_dir = folder / "tests"
test_dir.mkdir(exist_ok=True)
shutil.copyfile(native / "test_offline.py", test_dir / "test_offline.py")
config = json.loads((native / "config-probe-1.json").read_text())
config["supported_case_ids"] = [entry["case_id"] for entry in manifest["cases"]]
for camera in config["cameras"]:
    camera["pose_strategy"] = "source-bound ego-attached view; original pixel review required"
(folder / "config.json").write_text(json.dumps(config, indent=2) + "\n")
for item in primary["files"]:
    path = folder / item["path"]
    item["content"] = path.read_text()
primary["law_id"] = "NRS-484B-153-3"
(folder / "construction.json").write_text(json.dumps(primary, indent=2) + "\n")
plan_path = folder / "case-plan.json"
plan = json.loads(plan_path.read_text())
plan["camera_plan"] = {
    "profile": "overview1080-capability", "duration_s": config["duration_s"],
    "composition": "synchronized_four_view_primary",
    "coverage": [
        {"view": "overview", "subject": "driver, traffic-side door and passing vehicle",
         "interval": "full 600-frame capture"},
        {"view": "approach", "subject": "passing vehicle trajectory and road traffic side",
         "interval": "full 600-frame capture"},
        {"view": "reference_corner", "subject": "door hinge side and passenger/cargo transfer",
         "interval": "full 600-frame capture"},
        {"view": "driver_reference", "subject": "driver, door operation and transfer actor",
         "interval": "full 600-frame capture"}]}
for case in plan["cases"]:
    case["kind"] = "delivery"
    case["target_type"] = "judgment_sweep"
    case["unresolved_legal_necessity"] = True
for item in plan["source_observation_mapping"].items():
    term, mapping = item
    mapping["channels"] = [term]
    mapping["source_refs"] = ["native-door-trace.jsonl", "door-pixel-review.json",
                              "video_frames.jsonl"]
    mapping["evidence"] = "Original Native actor/frame joins plus independently reviewed four-camera pixels; actual source capture pending"
for disposition in plan["requirement_dispositions"]:
    disposition["evidence_or_gap"] = (
        "Four selected source-hashed CPU constructions, public compatibility, "
        "recorded-only and synthetic physical/lifecycle checks pass. "
        "Actual Native traffic-side door pose, transfer activity and contextual necessity remain for local source review.")
plan_path.write_text(json.dumps(plan, indent=2) + "\n")
print("canonical root entrypoint/config/construction/tests and 30 s four-camera plan materialized")
