"""Exact staged source preflight; live Native capture integration remains pending."""
import argparse
import hashlib
import json
from pathlib import Path

from geometry import CELLS, FRAMES, TURN_FIRST_FRAME, check as check_geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    direction, behavior = config["direction"], config["behavior"]
    if direction not in CELLS or behavior not in ("obey", "turn"):
        raise ValueError("Unknown signed turn case")
    cell_id, maneuver, sign_code, _ = CELLS[direction]
    if (config["cell_id"], config["law_id"], config["sign_code"]) != (
            cell_id, "LVMC-11-40-080", sign_code):
        raise ValueError("Frozen law/cell/sign identity differs")
    if config["duration_s"] != 30 or config["rate_hz"] != 20:
        raise ValueError("Exact 600-frame timebase differs")
    if sha(root / "road.xodr") != config["road_sha256"]:
        raise ValueError("Staged OpenDRIVE source changed")
    if sha(root / "source.jsonl") != config["source_sha256"]:
        raise ValueError("Staged route source changed")
    source = [json.loads(line) for line in (root / "source.jsonl").read_text().splitlines()]
    if len(source) != FRAMES or [row["frame"] for row in source] != list(range(FRAMES)):
        raise ValueError("Source frame inventory differs")
    if any(row["time_s"] != row["frame"]/20 or row["sign_code"] != sign_code or
           row["cell_id"] != cell_id or row["machine_class"] != "bicycle" or
           row["mounted"] is not True for row in source):
        raise ValueError("Source time, sign, class or posture plan differs")
    if source[TURN_FIRST_FRAME]["body_center_xy_m"] != [0, -8]:
        raise ValueError("Controlled turn start differs")
    if behavior == "obey" and source[-1]["body_center_xy_m"][0] != 0:
        raise ValueError("Obey branch contains a lateral turn")
    if behavior == "turn" and source[-1]["body_center_xy_m"][0] == 0:
        raise ValueError("Turn branch does not change heading")
    check_geometry(direction)
    return {"case_id":config["case_id"],"cell_id":cell_id,
            "behavior":behavior,"maneuver":maneuver,"sign_code":sign_code,
            "frames":FRAMES,"source_sha256":config["source_sha256"],
            "road_sha256":config["road_sha256"],"cpu_source_preflight_passed":True,
            "native_capture_executed":False,"delivery_ready":False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise ValueError("Staged source preflight supports --check only")
    print(json.dumps(check(),sort_keys=True))
