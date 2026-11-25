"""Materialize the selected top-level CPU return contract."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    construction = json.loads((ROOT / "construction-precedence.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    files = {item["path"]: item["content"] for item in construction["files"]}
    config = json.loads(files["config.json"])
    config["supported_case_ids"] = [item["case_id"] for item in plan["cases"]]
    config["case"] = plan["cases"][0]
    names = ("overview", "approach", "reference_corner", "driver_reference")
    sizes = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    config["cameras"] = [
        {"name": name, "width": size[0], "height": size[1],
         "pose_strategy": "ego mounted" if name == "driver_reference"
         else "fixed reviewed crossing view", "fov_deg": 90}
        for name, size in zip(names, sizes)]
    files["config.json"] = json.dumps(config, indent=2) + "\n"
    old = 'config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]'
    new = '[item["name"] for item in config["cameras"]] != ["overview", "approach", "reference_corner", "driver_reference"]'
    if files["runner.py"].count(old) != 1:
        raise ValueError("top-level runner camera check changed")
    files["runner.py"] = files["runner.py"].replace(old, new)
    for item in construction["files"]:
        item["content"] = files[item["path"]]
        target = ROOT / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    construction.update(
        mechanisms=["source-gated median opening roadway crossing and distinct public highways",
                    "original inoperative governing-signal readback and subsection 4 review",
                    "original body entry order and requested response measured separately"],
        measurement_plan={"precedence": "original other entry, other exit, ego entry and governing signal across 900 frames",
                          "advance": "matched crossing with ego entry before other exit; no legal cutoff"},
        static_checks=["reviewed OpenDRIVE roadway crossing and distinct public highway sources",
                       "governing signal identity, inoperative state, subsection 4 and opposing-turn applicability",
                       "source-joined 900 frame body and four-view histories"],
        termination_rules=["stop after planned 45 seconds or original-source failure"])
    (ROOT / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")


if __name__ == "__main__":
    build()
