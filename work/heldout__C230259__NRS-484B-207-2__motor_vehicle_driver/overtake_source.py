"""Join retained original overtaking sources; return measurements, not legal findings."""

import hashlib
import json
from pathlib import Path

from overtake_geometry import measure

ASSIGNMENT = "heldout__C230259__NRS-484B-207-2__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _required(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("Missing required source: " + name)
    return path


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("Empty original source: " + path.name)
    return rows


def analyze(attempt):
    """Require one exact case, original frame joins, and four retained cameras.

    The receipt binds every original byte stream. It does not certify physical
    visibility, subjective observation or hearing, or right-pass permission.
    """
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            config.get("law_id") != "NRS-484B-207-2" or
            config.get("cell_id") != "C230259" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("Wrong exact overtaking identity")
    names = ["overtake_site_original.json", "overtake_bodies_original.jsonl", "trace.jsonl", "video_frames.jsonl"]
    names += [name + ".mkv" for name in CAMERAS]
    names += [name + "-frames.jsonl" for name in CAMERAS]
    receipt = json.loads(_required(root, "overtake_source_receipt.json").read_text())
    if receipt.get("case_id") != case_id or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("Original overtaking receipt identity changed")
    digests = receipt.get("source_sha256")
    if not isinstance(digests, dict) or set(digests) != set(names):
        raise ValueError("Original overtaking receipt inventory incomplete")
    paths = {name: _required(root, name) for name in names}
    if any(not isinstance(digests[name], str) or _hash(path) != digests[name]
           for name, path in paths.items()):
        raise ValueError("Original overtaking source SHA-256 mismatch")
    if receipt.get("site_sha256") != digests["overtake_site_original.json"]:
        raise ValueError("Original Native road site receipt differs")
    bodies = _rows(paths["overtake_bodies_original.jsonl"])
    trace = _rows(paths["trace.jsonl"])
    mapping = _rows(paths["video_frames.jsonl"])
    if not len(bodies) == len(trace) == len(mapping):
        raise ValueError("Original overtaking frame inventories differ")
    for index, (body, motion, frame_map) in enumerate(zip(bodies, trace, mapping)):
        if (frame_map.get("video_frame") != index or
                frame_map.get("native_frame") != body.get("frame") or
                frame_map.get("time_s") != body.get("time_s") or
                motion.get("frame") != body.get("frame") or
                motion.get("time_s") != body.get("time_s")):
            raise ValueError("Original overtaking body, trace and video join differs")
        corners = body.get("ego", {}).get("body_corners_xy_m", [])
        position = motion.get("position", {})
        if len(corners) != 4 or any(
            abs(sum(corner[axis] for corner in corners) / 4 - position.get(key, float("inf"))) > 0.05
            for axis, key in enumerate(("x", "y"))
        ):
            raise ValueError("Original overtaking ego body/trace position differs")
        if abs(body["ego"]["speed_mps"] - motion.get("speed_mps", float("inf"))) > 0.01:
            raise ValueError("Original overtaking ego body/trace speed differs")
        if abs(motion.get("speed_mph", float("inf")) - motion["speed_mps"] / 0.44704) > 0.03:
            raise ValueError("Original overtaking trace mph/mps differs")
    for name in CAMERAS:
        rows = _rows(paths[name + "-frames.jsonl"])
        if len(rows) != len(bodies):
            raise ValueError("Original camera frame count differs: " + name)
        for index, (row, body) in enumerate(zip(rows, bodies)):
            if (row.get("video_frame") != index or row.get("native_frame") != body.get("frame") or
                    abs(row.get("time_s", float("inf")) - body["time_s"]) > .05):
                raise ValueError("Original camera frame join differs: " + name)
    ego_id = receipt.get("ego_actor_id")
    overtaker_id = receipt.get("overtaker_actor_id")
    geometry = measure(bodies, ego_id, overtaker_id)
    return {"case_id": case_id, "source_sha256": digests, "geometry": geometry,
            "source_notice": None, "source_right_pass_permission": None,
            "original_camera_streams": list(CAMERAS),
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "limitations": ["Original camera bytes and frame joins do not establish visibility or subjective notice.",
                            "Separate source review is required for right-pass permission."]}
