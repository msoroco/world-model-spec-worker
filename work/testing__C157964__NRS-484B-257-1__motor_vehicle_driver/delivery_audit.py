"""Independent original-source audit for the exact C157964 delivery cases.

Diagnostic self-tests exercise joins and decoding. Only a separately reviewed
Native attempt can satisfy the physical and pixel branches of this audit.
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
CASES = {"officer_active_stop_then_go", "officer_active_hold",
         "officer_present_inactive", "no_officer_yield_nearest_view"}


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
          decode_receipt=None, output=None):
    attempt = Path(attempt).resolve()
    suffix = case_id.removeprefix(HERE.name + "__")
    if suffix not in CASES or case_id != HERE.name + "__" + suffix:
        raise ValueError("Wrong selected exact case")
    provenance = read(attempt / "acquisition-provenance.json")
    if diagnostic_selftest:
        if provenance.get("provenance_kind") != "synthetic_fixture" or provenance.get("diagnostic_fixture") is not True:
            raise ValueError("Diagnostic selftest requires synthetic provenance")
    elif provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("Native non-diagnostic source required")
    config = read(attempt / "config.json")
    context = read(attempt / "officer_context.json")
    review = read(attempt / "officer_review.json")
    history = rows(attempt / "officer_history.jsonl")
    frames = rows(attempt / "video_frames.jsonl")
    if config.get("selected_case_id") != case_id or len(history) != len(frames) or len(history) != len(review.get("frames", [])):
        raise ValueError("Incomplete original officer source interval")
    if not diagnostic_selftest and len(frames) != round(config["duration_s"] * 20):
        raise ValueError("Incomplete Native source interval")
    if len(frames) < 3 or review.get("officer_history_sha256") != sha(attempt / "officer_history.jsonl"):
        raise ValueError("Original officer review source changed")
    cameras = {name: attempt / (name + ".mkv") for name in CAMERAS}
    media.check_four_view_sources(cameras)
    for name, path in cameras.items():
        if review.get("camera_sha256", {}).get(name) != sha(path):
            raise ValueError("Officer review camera source changed")
    signed = attempt / "officer-site.xodr"
    if sha(signed) != config["site"]["xodr_sha256"]:
        raise ValueError("Exact signed-entrance source changed")
    site = review.get("site_review", {})
    if site.get("sign_id") != config["site"]["yield_sign_id"] or site.get("source_camera") not in {name + ".mkv" for name in CAMERAS}:
        raise ValueError("Signed entrance lacks original-camera review")
    if site.get("proper_sign_judgment") != "unresolved" or site.get("nearest_view_judgment") != "unresolved":
        raise ValueError("Unresolved signed-entrance judgment was pre-decided")
    polygon = Polygon(context["intersection_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid original junction polygon")
    first_entry = None
    previous_native = -1
    first_time = history[0]["time_s"]
    for index, (row, frame, observed) in enumerate(zip(history, frames, review["frames"])):
        native = row.get("frame")
        if (type(native) is not int or native <= previous_native or frame.get("carla_frame") != native
                or observed.get("frame") != native or frame.get("video_frame") != index
                or row.get("time_s") != frame.get("time_s")
                or abs(row["time_s"] - first_time - index / 20) > .005):
            raise ValueError("Original officer frame/time join differs")
        previous_native = native
        if any(frame.get("camera_frames", {}).get(name) != native for name in CAMERAS):
            raise ValueError("Original camera frame join differs")
        if type(observed.get("through_highway_sight_clear")) is not bool or observed.get("sight_frame_source") not in {name + ".mkv" for name in CAMERAS}:
            raise ValueError("Missing original through-highway sight review")
        if row.get("through", {}).get("actor_id") != context.get("through_actor_id"):
            raise ValueError("Original through actor differs")
        body = MultiPoint(row["ego"]["body_vertices_xy_m"]).convex_hull
        if first_entry is None and body.intersects(polygon):
            first_entry = index
        expected = {"officer_active_stop_then_go": "active", "officer_active_hold": "active",
                    "officer_present_inactive": "inactive", "no_officer_yield_nearest_view": "absent"}[suffix]
        if expected == "absent" and row.get("officer_actor_id") is not None:
            raise ValueError("Absent-officer branch has an officer actor")
        if expected != "absent" and row.get("officer_actor_id") != context.get("officer_actor_id"):
            raise ValueError("Present-officer identity differs")
        if (observed.get("traffic_control_observed") is not (expected == "active")
                or observed.get("observed_direction") not in
                ({"stop", "go"} if expected == "active" else {"none"})):
            raise ValueError("Original officer-control branch differs")
    decoded = {name: media.audit(path, len(frames), mapping_sha256=sha(attempt / "video_frames.jsonl"))
               for name, path in cameras.items()}
    if not diagnostic_selftest:
        seal = read(attempt / "capture-seal.json")
        required = {"officer_history.jsonl", "officer_review.json", "officer_context.json",
                    "video_frames.jsonl", "officer-site.xodr", *(name + ".mkv" for name in CAMERAS)}
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
        if (result.get("case_id") != case_id or result.get("provenance_kind") != "native"
                or result.get("diagnostic_fixture") is not False
                or result.get("physical_acceptance_claimed") is not False
                or any(result.get("physical_checks", {}).get(key, {}).get("status") != "met"
                       for key in ("setup", "target", "maneuver", "attempt"))):
            raise ValueError("Native source result lacks measured physical completion")
        review_pixels = read(pixel_review) if pixel_review else None
        if (not isinstance(review_pixels, dict) or review_pixels.get("case_id") != case_id
                or not review_pixels.get("reviewer") or not review_pixels.get("observations")
                or review_pixels.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")
                or review_pixels.get("source_sha256") != {name: sha(path) for name, path in cameras.items()}):
            raise ValueError("Independent Native pixel review required")
        if {item.get("camera") for item in review_pixels["observations"]} != set(CAMERAS):
            raise ValueError("Pixel review omits original camera")
        if decode_receipt is None:
            raise ValueError("Independent primary-video decode receipt required")
        video, trace = attempt / "raw.mkv", attempt / "converted/trace.json"
        if not video.is_file() or not trace.is_file():
            raise ValueError("Saved primary video or converted trace missing")
        primary = media.audit(video, len(frames), mapping_sha256=sha(attempt / "video_frames.jsonl"),
                              receipt=Path(decode_receipt))
        if len(read(trace).get("scenes", [])) != len(frames):
            raise ValueError("Converted trace omits original frames")
    report = {"format": "worker-delivery-audit-diagnostic" if diagnostic_selftest else "worker-delivery-audit",
              "software_checks_passed": True, "passed": not diagnostic_selftest,
              "diagnostic_fixture": diagnostic_selftest, "physical_acceptance_claimed": False,
              "case_id": case_id, "source_frame_count": len(frames),
              "first_body_entry_frame": first_entry, "camera_audits": decoded,
              "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(__file__)}
    if not diagnostic_selftest:
        report.update({"source_result_sha256": sha(attempt / "result.json"),
                       "video": "raw.mkv", "video_sha256": sha(video),
                       "trace": "converted/trace.json", "trace_sha256": sha(trace),
                       "pixel_review_sha256": sha(pixel_review),
                       "source_decode_receipt_path": str(Path(decode_receipt).resolve()),
                       "source_decode_receipt_sha256": sha(decode_receipt),
                       "source_decode_auditor_sha256": primary["auditor_sha256"]})
    if output is not None:
        output = Path(output).resolve()
        if attempt not in output.parents or output.name == "result.json":
            raise ValueError("Audit report must stay under its original attempt")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-selftest", action="store_true")
    parser.add_argument("--pixel-review", type=Path)
    parser.add_argument("--decode-receipt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic_selftest=args.diagnostic_selftest,
                           pixel_review=args.pixel_review, decode_receipt=args.decode_receipt,
                           output=args.output), sort_keys=True))
