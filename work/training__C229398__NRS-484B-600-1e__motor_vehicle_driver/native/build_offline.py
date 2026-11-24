"""Bind unselected Native draft to pinned offline construction test."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = "training__C229398__NRS-484B-600-1e__motor_vehicle_driver__probe_03"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = [{"path": rel, "content": (ROOT / rel).read_text()}
             for rel in ("config.json", "runner.py", "tests/test_runner.py")]
    write(ROOT / "construction.json", {
        "format": "c229398-unselected-native-feasibility-v1", "case_id": CASE,
        "cell_id": "C229398", "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "recording_description": "30 s 20 Hz original approach-to-curb-park; four source cameras; measured velocity trace",
        "files": files,
    })
    write(ROOT / "manifest.json", {
        "format": "c229398-partial-offline-manifest-v1",
        "cases": [{"case_id": CASE, "construction": "construction.json",
                   "construction_sha256": sha(ROOT / "construction.json")}],
        "physical_completion": False,
    })
    print(json.dumps({"construction_sha256": sha(ROOT / "construction.json"),
                      "manifest_sha256": sha(ROOT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
