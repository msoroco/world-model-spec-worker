"""Materialize the canonical entrypoint and four-view CPU delivery shell."""
from __future__ import annotations

import json
from pathlib import Path


def write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def main() -> None:
    folder = Path(__file__).resolve().parent
    primary = json.loads((folder / "construction-dual_clear.json").read_text())
    files = {item["path"]: item["content"] for item in primary["files"]}
    config = json.loads(files["config.json"])
    ids = [entry["case_id"] for entry in json.loads(
        (folder / "execution-manifest.json").read_text())["cases"]]
    config.update(duration_s=45, rate_hz=20, supported_case_ids=ids,
                  source_packets=[], case={"case_id": ids[0],
                                           "recording_description": primary["recording_description"]})
    names = ("overview", "approach", "reference_corner", "driver_reference")
    sizes = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    subjects = ("whole surveyed intersection, ego and other-user positions",
                "approaching official head with both green aspects and ego",
                "crosswalk and conflict region with ego and other user",
                "driver sight toward official signal and crossing")
    config["cameras"] = [{"name": name, "width": size[0], "height": size[1],
                          "fov_deg": 75, "pose_strategy": "source-sealed site camera_poses"}
                         for name, size in zip(names, sizes)]
    write(folder / "config.json", config)
    (folder / "runner.py").write_text(files["runner.py"])
    construction_files = []
    for name in ("runner.py", "config.json", *[p for p in files if p.endswith(".py")
                                            and "/" not in p and p != "runner.py"]):
        construction_files.append({"path": name, "content": (folder / name).read_text()})
    construction = {"law_id": primary["law_id"], "cell_id": primary["cell_id"],
                    "actor": primary["actor"], "case_id": ids[0],
                    "entrypoint": "runner.py", "files": construction_files,
                    "recording_description": primary["recording_description"],
                    "measurement_plan": {"dual_aspect_straight_yield_measurement":
                                         "Join original official-head pixels, ego and other-user bodies, lawful-use packet provenance and geometry by frame; preserve legal uncertainty."},
                    "static_checks": ["source-sealed exact site and official head",
                                      "20 Hz four-camera capture and restoration",
                                      "source-joined packet and original body histories"],
                    "termination_rules": {"duration_s": 45,
                                          "early_termination": "retain unsealed failure; do not fabricate continuation"},
                    "mechanisms": ["source-surveyed dual-aspect head and straight route",
                                   "actual ego and other-user Native controllers",
                                   "four original camera views with independent lamp packets"]}
    write(folder / "construction.json", construction)
    plan_path = folder / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["camera_plan"] = {"profile": "overview1080-capability",
                           "duration_s": 45, "composition": "synchronized_four_view_primary",
                           "coverage": [{"view": view, "subject": subject,
                                         "interval": "all 900 original frames at 20 Hz"}
                                        for view, subject in zip(names, subjects)]}
    plan["source_observation_mapping"] = {}
    write(plan_path, plan)
    print(json.dumps({"canonical_case": ids[0], "covered_cases": len(ids)}))


if __name__ == "__main__":
    main()
