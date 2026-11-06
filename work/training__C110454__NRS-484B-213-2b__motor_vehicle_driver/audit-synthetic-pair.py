"""Independent audit of the C110454 local synthetic saved pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "../../.runtime-work/c110454-synthetic-native"
LIMIT = 30.48
measured = {}
for case in ("reference", "contrast"):
    path = OUT / (case + "-native-samples.json")
    rows = json.loads(path.read_text())
    if len(rows) != 480:
        raise ValueError("Incomplete synthetic source frames")
    if any(row["video_frame"] != index or row["native_frame"] != index or
           abs(row["time_s"] - index * .05) > 1e-6 for index, row in enumerate(rows)):
        raise ValueError("Saved frame/time join differs")
    if any(row["two_way_native_survey"] is not True for row in rows):
        raise ValueError("Two-way synthetic survey marker missing")
    left = [row for row in rows if min(point[1] for point in row["body_xy_m"]) > 0
            and max(point[0] for point in row["body_xy_m"]) < -7
            and row["speed_m_s"] > .05]
    if len(left) != 63:
        raise ValueError("Left-driving interval differs")
    distance = min(-7-max(point[0] for point in row["body_xy_m"]) for row in left)
    measured[case] = {"nearest_body_front_m": distance,
                      "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
if not (measured["reference"]["nearest_body_front_m"] > LIMIT >
        measured["contrast"]["nearest_body_front_m"]):
    raise ValueError("Controlled threshold relation differs")
if rows[-1]["body_xy_m"][0] != json.loads((OUT / "reference-native-samples.json").read_text())[-1]["body_xy_m"][0]:
    raise ValueError("Controlled parking endpoint differs")
print(json.dumps({"passed": True, "synthetic_only": True,
                  "independent_480_frame_pair_audit": measured,
                  "physical_or_legal_verdict": False}, sort_keys=True))
