"""Synthetic CPU proof of sight/speed source joining and fail-closed checks."""
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from sight_speed_measure import EXPECTED_ID, measure


def source(speed_mps):
    frames = []
    for i in range(600):
        distance = 40.0 - speed_mps * i / 20
        frames.append({
            "frame": i, "time_s": i / 20,
            "distance_to_boundary_m": distance,
            "ego_speed_mps": speed_mps,
            "within_intersection": -15 <= distance < 0,
            "intersection_clear_100ft": False,
            "entering_approach_views": {
                "north": {"clear_100ft": False,
                          "traffic_visible_100ft": False,
                          "source_ref": f"native/ray/north/{i}"},
                "east": {"clear_100ft": True,
                         "traffic_visible_100ft": True,
                         "source_ref": f"native/ray/east/{i}"}}})
    return {"assignment_id": EXPECTED_ID,
            "source_kind": "native_saved_observation",
            "frame_rate_hz": 20,
            "entering_approach_ids": ["north", "east"],
            "context": {
                "through_street": {"value": False,
                                   "source_ref": "native/map/priority/0"},
                "traffic_controlled_intersection": {
                    "value": False,
                    "source_ref": "native/map/control/0"}},
            "frames": frames}


def write_and_measure(root, data, name):
    path = root / f"{name}.json"
    raw = json.dumps(data, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return measure(path, hashlib.sha256(raw).hexdigest())


def rejected(root, data, name, message):
    try:
        write_and_measure(root, data, name)
    except ValueError as error:
        assert message in str(error), (name, str(error))
        print(f"REJECT {name}: {error}")
    else:
        raise AssertionError(f"accepted invalid {name}")


def main():
    assert Path(os.environ["TMPDIR"]).resolve().parts[-1] == ".runtime-work"
    with tempfile.TemporaryDirectory(prefix="c24758-sight-", dir=os.environ["TMPDIR"]) as tmp:
        root = Path(tmp)
        low = source(6.2)
        high = source(7.2)
        a = write_and_measure(root, low, "reference")
        b = write_and_measure(root, high, "contrast")
        assert a["frame_count"] == b["frame_count"] == 600
        assert a["sight_limited_frame_count"] > 0
        assert b["traversal_speed_mph_max"] > a["traversal_speed_mph_max"]
        assert a["legal_verdict"] is b["legal_verdict"] is None
        print("PASS positive paired 600-frame/20-Hz sight-limited traversal")
        print("reference max mph", a["traversal_speed_mph_max"])
        print("contrast max mph", b["traversal_speed_mph_max"])

        changed = copy.deepcopy(low)
        changed["frames"][300]["ego_speed_mps"] = 9
        p = root / "reference.json"
        p.write_text(json.dumps(changed))
        try:
            measure(p, a["source_sha256"])
        except ValueError as error:
            assert "source sha256 mismatch" in str(error)
            print("REJECT changed source hash")
        else:
            raise AssertionError("changed source accepted")

        wrong = copy.deepcopy(low)
        wrong["context"]["through_street"]["value"] = None
        rejected(root, wrong, "unresolved_exception", "unresolved exception")
        wrong = copy.deepcopy(low)
        del wrong["frames"][50]["entering_approach_views"]["east"]
        rejected(root, wrong, "missing_approach", "view inventory mismatch")
        wrong = copy.deepcopy(low)
        wrong["frames"][200]["time_s"] = 11.0
        rejected(root, wrong, "time_join", "frame/time join mismatch")
        wrong = copy.deepcopy(low)
        wrong["frames"] = wrong["frames"][:599]
        rejected(root, wrong, "short_capture", "incomplete 30-second trace")
        print("PASS 5 fail-closed negatives")


if __name__ == "__main__":
    main()
