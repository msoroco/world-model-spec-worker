"""Check the materialized C125751 CPU package without starting CARLA."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from camera_setup import SIZES
from runner import TARGETS
from site_packet import verify_site_packet

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    construction = json.loads((HERE / "construction.json").read_text())
    config = json.loads((HERE / "config.json").read_text())
    cases = {case["case_id"] for case in plan["cases"]}
    if cases != set(TARGETS) or cases != set(config["supported_case_ids"]):
        raise ValueError("Top-level case coverage differs from tested runner")
    if construction["entrypoint"] != "runner.py":
        raise ValueError("Unexpected Native entrypoint")
    for entry in construction["files"]:
        path = REPO / entry["source"] if entry.get("source") else HERE / entry["path"]
        if path.read_text() != entry["content"]:
            raise ValueError("Materialized source differs: " + entry["path"])
    cameras = {item["name"]: (item["width"], item["height"]) for item in config["cameras"]}
    if cameras != SIZES or plan["camera_plan"]["duration_s"] != config["duration_s"]:
        raise ValueError("Camera profile or duration differs")
    packet = verify_site_packet(config, HERE)
    if not packet["diagnostic_only"] or packet["physical_site_verified"]:
        raise ValueError("Synthetic site fixture lost its diagnostic qualification")
    for case in sorted(cases):
        if case == config["selected_case_id"]:
            config_path = HERE / "config.json"
        else:
            suffix = case.rsplit("__", 1)[-1]
            bundle = json.loads((HERE / ("diagnostic-construction-" + suffix + ".json")).read_text())
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for entry in bundle["files"]:
                    if entry["path"].endswith(".json") and not entry.get("source"):
                        (root / entry["path"]).write_text(entry["content"])
                _check(root / "config.json", case)
            continue
        _check(config_path, case)
    print(json.dumps({"cases_checked": len(cases), "materialized_files": len(construction["files"]),
                      "site": "synthetic_diagnostic_only", "carla_started": False}, sort_keys=True))


def _check(path, case):
    result = subprocess.run([sys.executable, str(HERE / "runner.py"), "--config", str(path), "--check"],
                            check=True, capture_output=True, text=True)
    receipt = json.loads(result.stdout)
    if receipt["case_id"] != case or receipt["carla_started"] or receipt["frames"] != 1100:
        raise ValueError("Runner CPU check differs from planned case")


if __name__ == "__main__":
    main()
