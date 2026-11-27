"""Offline identity and selected-source bundle check for seven rail targets."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def main():
    scenes = sorted((HERE / "cases").glob("*/scene.json"))
    if len(scenes) != 7:
        raise ValueError("rail selected scene count differs")
    for scene in scenes:
        bundle = json.loads((scene.parent / "construction.json").read_text())
        if bundle["case_id"] != json.loads(scene.read_text())["case_id"]:
            raise ValueError("rail scene and construction differ")
        for entry in bundle["files"]:
            source = HERE / entry["path"] if entry.get("source") else scene.parent / entry["path"]
            if source.read_text() != entry["content"]:
                raise ValueError("rail construction content differs: " + entry["path"])
        process = subprocess.run(
            [sys.executable, str(HERE / "runner.py"), "--check", "--case", str(scene)],
            capture_output=True, text=True, check=True)
        report = json.loads(process.stdout)
        if report["case_id"] != bundle["case_id"] or not report["offline_identity_checked"]:
            raise ValueError("rail offline identity differs")
        print(report["case_id"] + " construction and offline identity pass")
    print("7/7 selected construction bundles pass")


if __name__ == "__main__":
    main()
