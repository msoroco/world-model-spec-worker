"""Independent source audit for a saved NRS 484B.307(6)(a) attempt.

Diagnostic self-tests exercise software joins only. They cannot be accepted as
Native physical or legal evidence.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange import media

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CASES = {"entry_before_red", "entry_at_red", "entry_after_red", "stops_on_yellow"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt, case_id, *, diagnostic_selftest=False, pixel_review=None,
          output=None, decode_receipt=None):
    attempt = Path(attempt).resolve()
    suffix = case_id.removeprefix(HERE.name + "__")
    if suffix not in CASES or case_id != HERE.name + "__" + suffix:
        raise ValueError("Wrong selected exact case")
    context = read(attempt / "junction_context.json")
    provenance = read(attempt / "acquisition-provenance.json")
    if diagnostic_selftest:
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("Diagnostic selftest requires synthetic provenance")
    elif provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("Native non-diagnostic source required")
    history = rows(attempt / "signal_vehicle_history.jsonl")
    frames = rows(attempt / "video_frames.jsonl")
    if len(history) != 900 or len(frames) != 900:
        raise ValueError("Incomplete original source interval")
    polygon = Polygon(context["intersection_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid original intersection polygon")
    first_entry = red = None
    previous_inside = False
    previous_state = None
    first_time = history[0].get("time_s")
    previous_native = -1
    for index, (row, frame) in enumerate(zip(history, frames)):
        native = row.get("frame")
        if (type(native) is not int or native <= previous_native or
                frame.get("carla_frame") != native or
                frame.get("video_frame") != index or row.get("time_s") != frame.get("time_s") or
                type(first_time) not in (int, float) or
                abs(row["time_s"] - first_time - index / 20) > .005):
            raise ValueError("Original frame/time join differs")
        previous_native = native
        if (row.get("native_signal_id") != context.get("native_signal_id") or
                row.get("road_id") != context.get("governed_road_id") or
                row.get("lane_id") != context.get("governed_lane_id")):
            raise ValueError("Original governed signal or lane differs")
        if row.get("signal_state") not in ("Green", "Yellow", "Red"):
            raise ValueError("Invalid original signal state")
        inside = MultiPoint(row["ego_body_vertices_xy_m"]).convex_hull.intersects(polygon)
        if inside and not previous_inside and first_entry is None:
            first_entry = index
        if previous_state == "Yellow" and row["signal_state"] == "Red" and red is None:
            red = index
        previous_inside, previous_state = inside, row["signal_state"]
    if red is None:
        raise ValueError("Original Yellow-to-Red transition missing")
    expected = ((first_entry is not None and first_entry < red) if suffix == "entry_before_red" else
                first_entry == red if suffix == "entry_at_red" else
                (first_entry is not None and first_entry > red) if suffix == "entry_after_red" else
                first_entry is None)
    if not expected:
        raise ValueError("Original body-entry branch differs")
    cameras = {name: attempt / (name + ".mkv") for name in CAMERAS}
    media.check_four_view_sources(cameras)
    decoded = {name: media.audit(path, 900,
                                 mapping_sha256=sha(attempt / "video_frames.jsonl"))
               for name, path in cameras.items()}
    result = None
    if not diagnostic_selftest:
        seal = read(attempt / "capture-seal.json")
        required = {"junction_context.json", "acquisition-provenance.json",
                    "signal_vehicle_history.jsonl", "video_frames.jsonl",
                    *(name + ".mkv" for name in CAMERAS)}
        if seal.get("format") != "worker-sealed-capture" or not required <= set(seal.get("sources", {})):
            raise ValueError("Native capture seal omits original source")
        for name, digest in seal["sources"].items():
            if sha(attempt / name) != digest:
                raise ValueError("Sealed original source changed: " + name)
        if read(attempt / "native-exit.json").get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
            raise ValueError("Native exit does not bind original seal")
        if read(attempt / "owner-release.json").get("native_exit_sha256") != sha(attempt / "native-exit.json"):
            raise ValueError("Owner release does not bind Native exit")
        result = read(attempt / "result.json")
        if (result.get("case_id") != case_id or result.get("provenance_kind") != "native" or
                result.get("diagnostic_fixture") is not False or
                result.get("physical_acceptance_claimed") is not False or
                any(result.get("physical_checks", {}).get(key, {}).get("status") != "met"
                    for key in ("setup", "target", "maneuver", "attempt")) or
                not result.get("realized_observables")):
            raise ValueError("Native source result lacks measured physical completion")
        if not isinstance(pixel_review, Path) or not pixel_review.is_file():
            raise ValueError("Independent Native pixel review required")
        review = read(pixel_review)
        if (review.get("case_id") != case_id or not review.get("reviewer") or
                not review.get("method") or
                review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
                review.get("source_sha256") != {name: sha(path) for name, path in cameras.items()}):
            raise ValueError("Independent Native pixel review binding differs")
        samples = review.get("observations", [])
        if not samples or {row.get("camera") for row in samples} != set(CAMERAS):
            raise ValueError("Independent pixel review omits a required camera")
        from worker_exchange.capture import PROFILE
        dimensions = {"overview": PROFILE["overview"],
                      **dict(zip(CAMERAS[1:], PROFILE["detail_views"]))}
        for name, path in cameras.items():
            expected = [row for row in samples if row.get("camera") == name]
            width, height = dimensions[name]
            for row in expected:
                box = row.get("bbox_xyxy")
                if (type(row.get("video_frame")) is not int or not 0 <= row["video_frame"] < 900 or
                        not isinstance(box, list) or len(box) != 4 or
                        not all(type(x) is int for x in box) or
                        not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height) or
                        (box[2] - box[0]) * (box[3] - box[1]) < 16):
                    raise ValueError("Invalid independent pixel review box")
            pending = {row["video_frame"]: row for row in expected}
            seen = set()

            def inspect(frame):
                if (frame.width, frame.height) != (width, height):
                    raise ValueError("Reviewed camera dimensions differ")
                row = pending.get(frame.index)
                if row is None:
                    return
                x0, y0, x1, y1 = row["bbox_xyxy"]
                pixels = {frame.pixels[3 * (y * width + x):3 * (y * width + x) + 3]
                          for y in range(y0, y1) for x in range(x0, x1)}
                if len(pixels) < 2:
                    raise ValueError("Reviewed signal/actor ROI has no original pixel detail")
                seen.add(frame.index)

            media.audit(path, 900, checkers={"reviewed_pixels": (sha(__file__), inspect)},
                        mapping_sha256=sha(attempt / "video_frames.jsonl"))
            if seen != set(pending):
                raise ValueError("Independent pixel review frame was not decoded")
        if not isinstance(decode_receipt, Path):
            raise ValueError("Independent source decode receipt required")
        video = attempt / "raw.mkv"
        trace = attempt / "converted/trace.json"
        if not video.is_file() or not trace.is_file():
            raise ValueError("Saved primary video or converted trace missing")
        decoded_primary = media.audit(video, 900,
                                      mapping_sha256=sha(attempt / "video_frames.jsonl"),
                                      receipt=decode_receipt)
        scenes = read(trace).get("scenes", [])
        if len(scenes) != 900 or any(scene.get("t") != round(frame["time_s"] * 1000)
                                     for scene, frame in zip(scenes, frames)):
            raise ValueError("Converted trace and original frame times differ")
    report = {"format": "worker-delivery-audit-diagnostic" if diagnostic_selftest else
              "worker-delivery-audit", "software_checks_passed": True,
            "passed": not diagnostic_selftest, "diagnostic_fixture": diagnostic_selftest,
            "physical_acceptance_claimed": False,
            "case_id": case_id, "red_onset_frame": red, "first_body_entry_frame": first_entry,
            "source_sha256": {name: sha(attempt / name) for name in
                              ("junction_context.json", "acquisition-provenance.json",
                               "signal_vehicle_history.jsonl", "video_frames.jsonl")},
            "camera_audits": decoded, "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(__file__)}
    if not diagnostic_selftest:
        report.update({"source_result_sha256": sha(attempt / "result.json"),
                       "video": "raw.mkv", "video_sha256": sha(attempt / "raw.mkv"),
                       "trace": "converted/trace.json", "trace_sha256": sha(attempt / "converted/trace.json"),
                       "pixel_review_sha256": sha(pixel_review),
                       "source_decode_receipt_path": str(decode_receipt.resolve()),
                       "source_decode_receipt_sha256": sha(decode_receipt),
                       "source_decode_auditor_sha256": decoded_primary["auditor_sha256"]})
    if output is not None:
        output = Path(output).resolve()
        if attempt not in output.parents or output.name == "result.json":
            raise ValueError("Audit report must be written under its original attempt")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-selftest", action="store_true")
    parser.add_argument("--pixel-review", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--decode-receipt", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case,
                           diagnostic_selftest=args.diagnostic_selftest,
                           pixel_review=args.pixel_review, output=args.output,
                           decode_receipt=args.decode_receipt), sort_keys=True))
