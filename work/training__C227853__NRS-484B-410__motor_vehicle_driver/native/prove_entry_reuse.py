"""Check the existing off-highway construction proposed for the entry branch.

This proof does not authorize a supplemental binding or a physical capture.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_ID = "training__C177626__NRS-484B-260__motor_vehicle_driver"
SOURCE = ROOT / "work" / SOURCE_ID


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment_path = ROOT / "inputs" / SOURCE_ID / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    assert assignment["cell_id"] == "C177626"
    assert assignment["actor"] == "motor_vehicle_driver"
    assert assignment["cell"]["maneuver"] == "enter_road"
    assert assignment["cell"]["layout"] == "paved_road"
    runner = SOURCE / "runner.py"
    geometry = SOURCE / "geometry.py"
    result = subprocess.run([sys.executable, "-B", str(runner), "--check"],
                            cwd=SOURCE, text=True, capture_output=True, check=True)
    detail = json.loads(result.stdout)
    assert detail["road_ids"] == [1, 2]
    assert detail["conflict_xy_m"] == [2.0, -2.0]
    assert "Native road and lane readback required" in detail["source"]
    print(json.dumps({"passed": True, "source_assignment": SOURCE_ID,
                      "source_assignment_sha256": digest(assignment_path),
                      "runner_sha256": digest(runner), "geometry_sha256": digest(geometry),
                      "runner_check": detail, "binding_authorized": False,
                      "physical_entry_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
