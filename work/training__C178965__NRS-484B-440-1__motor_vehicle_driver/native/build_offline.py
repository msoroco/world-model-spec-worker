"""Bind exact C178965 Native proposal to runtime offline."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = "training__C178965__NRS-484B-440-1__motor_vehicle_driver__probe_02"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = [{"path": rel, "content": (ROOT / rel).read_text()}
             for rel in ("config.json", "runner.py", "tests/test_runner.py")]
    write(ROOT / "construction.json", {
        "format": "c178965-exact-native-proposal-v1", "case_id": CASE,
        "cell_id": "C178965", "actor": "motor_vehicle_driver",
        "entrypoint": "runner.py",
        "recording_description": "30 s, 20 Hz highway roadside stop with two vehicles and four original cameras",
        "files": files,
    })
    write(ROOT / "manifest.json", {
        "format": "c178965-partial-offline-manifest-v1",
        "cases": [{"case_id": CASE, "construction": "construction.json",
                   "construction_sha256": sha(ROOT / "construction.json")}],
        "physical_completion": False,
    })
    print(json.dumps({"construction_sha256": sha(ROOT / "construction.json"),
                      "manifest_sha256": sha(ROOT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
