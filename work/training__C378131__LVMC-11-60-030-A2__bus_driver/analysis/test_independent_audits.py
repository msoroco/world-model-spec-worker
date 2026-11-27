"""Source-bound positive and missing-source/change negatives on textual fixtures."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from independent_audits import SOURCE_FILES, audit_source, audit_comparison
from saved_only import extract
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.bus_scene import road_xml


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(prefix="bus-audit-") as temporary:
    root = Path(temporary)
    rows = []
    for i in range(600):
        row = {"native_frame": i + 100, "video_frame": i, "time_s": i / 20,
               "source_cameras": {name: i + 100 for name in ("overview", "approach", "reference_corner", "driver_reference")},
               "camera_rgb_sha256": {name: "a" * 64 for name in ("overview", "approach", "reference_corner", "driver_reference")},
               "body_vertices_m": [[-14, -3, 0], [-14, -1, 0],
                                   [-12, -3, 0], [-12, -1, 0]],
               "bus_speed_mps": 0.0,
               "door_open_request_active": 140 <= i < 420,
               "actual_door_state_observed": False,
               "actual_passenger_transfer_observed": False}
        rows.append(row)
    sources = {"native_map": "road.xodr", "motion": "bus_motion.jsonl",
               "bus_body": "bus_body.jsonl", "passenger_body": "passenger_body.jsonl",
               "camera_manifest": "video_frames.jsonl"}
    (root / sources["native_map"]).write_text(road_xml() + "\n")
    for key in SOURCE_FILES[1:]:
        (root / sources[key]).write_text("".join(json.dumps(row) + "\n" for row in rows))
    context = {"source_kind": "synthetic_native_sample", "physical_acceptance_claimed": False,
               "zone_kind_requested": "route_destination", "zone_id": "loading-place-378131",
               "route_id_requested": "R-378131",
               "vehicle_class_requested": "route_bus_non_tour", "emergency_requested": False,
               "designation_authority_confirmed": False,
               "source_files": sources,
               **{key + "_sha256": hash_file(root / name) for key, name in sources.items()}}
    assert audit_source(root, context, fixture=True)["frame_count"] == 600
    (root / "bus_context.json").write_text(json.dumps(context) + "\n")
    saved = extract(root, root / "saved-measurement.json", fixture=True)
    assert saved["stopped_door_request_frames_measured"] == 280
    assert saved["actual_passenger_transfer"] == "unknown_pending_original_pixel_review"
    try:
        extract(root, root / "another-measurement.json")
    except ValueError as error:
        assert "original Native source kind missing" in str(error)
    else:
        raise AssertionError("synthetic source passed original saved path")
    far = root / "far"
    far.mkdir()
    for name in sources.values():
        shutil.copyfile(root / name, far / name)
    distant = [{**row, "body_vertices_m": [[40, -3, 0], [40, -1, 0],
                                           [42, -3, 0], [42, -1, 0]]} for row in rows]
    (far / sources["bus_body"]).write_text("".join(json.dumps(row) + "\n" for row in distant))
    distant_context = {**context, "bus_body_sha256": hash_file(far / sources["bus_body"])}
    (far / "bus_context.json").write_text(json.dumps(distant_context) + "\n")
    try:
        extract(far, far / "saved.json", fixture=True)
    except ValueError as error:
        assert "no original bus body in authored loading segment" in str(error)
    else:
        raise AssertionError("distant bus body passed loading segment")
    for key, expected in [("motion", "stale source hash"), ("camera_manifest", "stale source hash")]:
        bad = copy.deepcopy(context)
        bad[key + "_sha256"] = "0" * 64
        try:
            audit_source(root, bad, fixture=True)
        except ValueError as error:
            assert expected in str(error)
        else:
            raise AssertionError("missing source-hash rejection: " + key)
    try:
        audit_source(root, context)
    except ValueError as error:
        assert "original Native source kind missing" in str(error)
    else:
        raise AssertionError("fixture passed as original")

fixed = {key: "same" for key in ("cell_id", "street_id", "route_id", "vehicle_class",
                                  "weather_id", "controller_id", "capture_profile", "loading_purpose")}
left = {**fixed, "source_kind": "original_native_bus_readback", "source_audit_sha256": "a" * 64,
        "physical_completion": "reviewed_original", "designation_authority_source_sha256": "b" * 64,
        "stopped_loading_reviewed": True, "passenger_exchange_reviewed": True,
        "zone_kind": "route_destination", "emergency_context": "none"}
right = {**left, "zone_kind": "other_street", "source_audit_sha256": "c" * 64}
assert audit_comparison(left, right, difference="zone_kind")["legal_outcome"] == "unresolved"
for name, change, message in [
    ("source", lambda item: item.pop("source_audit_sha256"), "original audited source"),
    ("physical", lambda item: item.update(physical_completion="unreviewed"), "physical completion review"),
    ("authority", lambda item: item.pop("designation_authority_source_sha256"), "designation authority"),
    ("fixed", lambda item: item.update(route_id="other"), "fixed condition differs"),
    ("difference", lambda item: item.update(zone_kind="route_destination"), "declared difference absent"),
]:
    bad = copy.deepcopy(right)
    change(bad)
    try:
        audit_comparison(left, bad, difference="zone_kind")
    except ValueError as error:
        assert message in str(error), (name, str(error))
    else:
        raise AssertionError("missing comparison rejection: " + name)

print("source and saved-only positive, five source/geometry negatives, comparison positive and five negatives passed")
