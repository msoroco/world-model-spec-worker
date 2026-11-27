"""Independent source audit for saved divided-road U-turn measurements.

Diagnostic mode tests the source joins. Original mode additionally requires a
sealed Native acquisition; neither mode decides authority or legal compliance.
"""

import argparse
import hashlib
import json
from pathlib import Path

from measure_uturn import measure_attempt

CAMERAS = ("overview", "approach", "median_reference", "driver_reference")
SOURCES = ("request.json", "divided-road-context.json", "source-review.json",
           "native-uturn.jsonl", "video_frames.jsonl")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if not Path(path).is_file():
        raise ValueError("Missing original delivery source: " + Path(path).name)
    return json.loads(Path(path).read_text())


def audit(attempt, report_path, diagnostic=False):
    attempt = Path(attempt).resolve()
    report = read(report_path)
    result = read(attempt / "result.json")
    config = read(attempt / "config.json")
    construction = read(attempt / "construction.json")
    request = read(attempt / "request.json")
    case = request.get("case_id")
    if not case or any(item.get("case_id") != case for item in (report, result, construction)) or config.get("selected_case_id") != case:
        raise ValueError("Saved exact U-turn case identity differs")
    measurement = measure_attempt(attempt)
    if report.get("format") != "worker-analysis-report" or report.get("source_complete") is not True:
        raise ValueError("Saved analysis report incomplete")
    if report.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("Saved provenance differs from audit mode")
    sources = {name: digest(attempt / name) for name in SOURCES}
    for name in ("right_hand_roadway", "divider_crossing", "u_turn_event",
                 "opening_geometry", "authority_context"):
        entry = report.get("measurements", {}).get(name, {})
        if entry.get("sources") != sources or entry.get("value") != measurement:
            raise ValueError("Saved measurement or source hash differs: " + name)
    if result.get("measured_values") != measurement or result.get("accepted") is not False:
        raise ValueError("Saved result or acceptance claim differs")
    if (measurement.get("authority_verified") is not False or
            measurement.get("legal_judgment") != "unresolved"):
        raise ValueError("Authority or legal conclusion was inferred")
    if result.get("video_references") != [name + ".mkv" for name in CAMERAS] or result.get("video_frame_map_reference") != "video_frames.jsonl":
        raise ValueError("Four original camera references missing")
    for name in CAMERAS:
        if not (attempt / (name + ".mkv")).is_file():
            raise ValueError("Missing original camera source: " + name)
    for name in ("ego_pose", "median_crossing_location"):
        channel = attempt / "channels" / (name + ".jsonl")
        if not channel.is_file() or len(channel.read_text().splitlines()) != 600:
            raise ValueError("Saved 600-frame channel incomplete: " + name)
    if not diagnostic:
        provenance = read(attempt / "acquisition-provenance.json")
        seal = read(attempt / "capture-seal.json")
        context = read(attempt / "divided-road-context.json")
        authority = read(attempt / "source-review.json")
        if (provenance.get("provenance_kind") != "native" or
                provenance.get("diagnostic_fixture") is not False or
                context.get("source_kind") != "original_native_divided_road_readback" or
                len(context.get("native_roadways", [])) != 2 or
                len(context.get("median_objects", [])) != 2 or
                seal.get("format") != "worker-sealed-capture" or
                seal.get("provenance_kind") != "native" or
                seal.get("frames") != 600 or
                seal.get("restoration", {}).get("restored") is not True or
                seal.get("encoder_exit_codes") != {name: 0 for name in CAMERAS}):
            raise ValueError("Sealed original Native road and median source missing")
        sealed_sources = seal.get("sources", {})
        for name in (*(source for source in SOURCES if source != "source-review.json"),
                     "trace.jsonl", "body_history.jsonl",
                     "capture/evidence.jsonl", *(camera + ".mkv" for camera in CAMERAS)):
            if sealed_sources.get(name) != digest(attempt / name):
                raise ValueError("Sealed original source hash differs: " + name)
        if (authority.get("review_status") != "independently_reviewed" or
                not authority.get("independent_reviewer") or
                authority.get("public_authority_establishment") not in
                    ("verified_opening", "not_established", "undetermined")):
            raise ValueError("Independent public-authority establishment review missing")
    return {"format": "c82860-independent-delivery-source-audit-v1",
            "case_id": case, "source_hashes": sources,
            "camera_source_hashes": {name: digest(attempt / (name + ".mkv")) for name in CAMERAS},
            "original_native_gate_checked": not diagnostic,
            "source_joins_passed": True, "physical_or_legal_acceptance": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.report, args.diagnostic), indent=2))
