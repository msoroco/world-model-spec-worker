"""Source-byte and Native-frame joins for the bus stationary diagnostic."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bus_standing import CAMERAS, measure_saved
from test_bus_standing import fixture


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


frames, context = fixture()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    designation = b'{"review_status":"source_only; authority unverified"}\n'
    put(root, "authority/route-R-1.json", designation)
    context["zone"]["designation_source"]["sha256"] = hashlib.sha256(designation).hexdigest()
    put(root, "bus-context.json", json.dumps(context).encode())
    history = []
    maps = []
    for index, frame in enumerate(frames):
        history.append({"video_frame": index, "native_frame": 1000 + index,
                        "time_s": frame["sim_time_s"],
                        "bus_speed_mps": frame["bus_speed_mps"],
                        "parking_brake_applied": frame["parking_brake_applied"],
                        "driver_present": frame["driver_present"],
                        "occupied_zone_id": frame["occupied_zone_id"]})
        maps.append({"video_frame": index, "native_frame": 1000 + index,
                     "camera_native_frames": {name: 1000 + index for name in CAMERAS}})
    put(root, "bus-history.jsonl", ("\n".join(map(json.dumps, history)) + "\n").encode())
    put(root, "video_frames.jsonl", ("\n".join(map(json.dumps, maps)) + "\n").encode())
    for name in CAMERAS:
        put(root, name + ".mkv", (name + "-diagnostic-only").encode())
    value = measure_saved(root, source_kind="synthetic_native_sample")
    assert value["stationary_frames"] == 100
    assert value["designation_authority_verified"] is False
    print("positive saved-source join")
    for label, name, data, expected in (
        ("designation", "authority/route-R-1.json", b"changed", "hash differs"),
        ("camera", "right.mkv", None, "missing required source"),
        ("frame", "video_frames.jsonl", ("\n".join(map(json.dumps, [dict(maps[0], native_frame=9), *maps[1:]])) + "\n").encode(), "identities differ"),
    ):
        original = (root / name).read_bytes()
        if data is None:
            (root / name).unlink()
        else:
            put(root, name, data)
        try:
            measure_saved(root, source_kind="synthetic_native_sample")
        except ValueError as error:
            assert expected in str(error), (label, str(error))
            print("negative", label, str(error))
        else:
            raise AssertionError("missing rejection: " + label)
        put(root, name, original)
