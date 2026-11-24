"""Bind the exact Native proposal into a pinned runtime offline construction."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver__probe_02"


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = []
    for rel in ("config.json", "runner.py", "tests/test_runner.py"):
        files.append({"path": rel, "content": (ROOT / rel).read_text()})
    construction = {
        "format": "c151707-exact-native-proposal-v1",
        "case_id": CASE,
        "cell_id": "C151707",
        "actor": "motor_vehicle_driver",
        "entrypoint": "runner.py",
        "recording_description": "30 s, 20 Hz one-way property route with four original camera streams",
        "files": files,
    }
    write(ROOT / "construction.json", construction)
    manifest = {"format": "c151707-partial-offline-manifest-v1",
                "cases": [{"case_id": CASE, "construction": "construction.json",
                           "construction_sha256": digest(ROOT / "construction.json")}],
                "physical_completion": False}
    write(ROOT / "manifest.json", manifest)
    print(json.dumps({"construction_sha256": manifest["cases"][0]["construction_sha256"],
                      "manifest_sha256": digest(ROOT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
