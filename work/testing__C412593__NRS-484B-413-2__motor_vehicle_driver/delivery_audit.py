"""Independent original-source and media audit for one right-turn attempt.

The diagnostic mode exercises the software path on synthetic CPU fixtures.
Actual delivery still requires Native provenance and independent pixel review.
"""

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "runtime/scenario_pipeline"))
from worker_exchange.media import audit as audit_video, check_four_view_sources

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + str(path))
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError("Empty original source: " + str(path))
    return result


def audit(attempt, case_id, diagnostic_fixture=False):
    attempt = Path(attempt)
    if not case_id.startswith(HERE.name + "__"):
        raise ValueError("Wrong exact C412593 case")
    config = json.loads((attempt / "config.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if (config.get("selected_case_id") != case_id or result.get("case_id") != case_id
            or config.get("cell_id") != "C412593" or config.get("law_id") != "NRS-484B-413-2"):
        raise ValueError("Exact case identity differs")
    if diagnostic_fixture:
        if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
            raise ValueError("Diagnostic flag requires synthetic provenance")
    else:
        if result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is True:
            raise ValueError("Native source provenance required")
        check = result.get("physical_checks", {}).get("maneuver", {})
        if not result.get("maneuver_completed") or check.get("status") != "met":
            raise ValueError("Original physical completion proof required")
    mapping = rows(attempt / "video_frames.jsonl")
    drive = rows(attempt / "drive_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    count = len(mapping)
    if any(len(source) != count for source in (drive, trace, evidence)):
        raise ValueError("Full original source frame coverage required")
    if not diagnostic_fixture and count != config["rate_hz"] * config["duration_s"]:
        raise ValueError("Native duration differs from capture contract")
    previous = None
    for index, frame in enumerate(mapping):
        fid, time = frame.get("carla_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or type(fid) is not int or
                type(time) not in (int, float) or not math.isfinite(time)):
            raise ValueError("Original frame map invalid")
        if previous and (fid <= previous[0] or time <= previous[1]):
            raise ValueError("Original frame order invalid")
        previous = (fid, time)
        sample = drive[index]
        if (sample.get("frame") != fid or trace[index].get("frame") != fid or
                evidence[index].get("original_frame") != fid):
            raise ValueError("Original participant/frame join invalid")
        if abs(sample.get("time_s", -math.inf) - time) > 1e-5:
            raise ValueError("Original drive timestamp join invalid")
        body = sample.get("body_vertices_m")
        if not isinstance(body, list) or len(body) < 4:
            raise ValueError("Complete original vehicle body is missing")
        if type(sample.get("right_indicator")) is not bool or type(sample.get("ego_road_id")) is not int:
            raise ValueError("Original indicator or road readback missing")
    for name, digest in result.get("source_evidence_hashes", {}).items():
        if sha(attempt / name) != digest:
            raise ValueError("Sealed original source hash differs: " + name)
    cameras = {name: attempt / (name + ".mkv") for name in CAMERAS}
    check_four_view_sources(cameras)
    decoded = {}
    for name, path in cameras.items():
        receipt = audit_video(path, count, mapping_sha256=sha(attempt / "video_frames.jsonl"))
        if not receipt.get("rgb_sequence_sha256"):
            raise ValueError("Decoded pixels missing")
        decoded[name] = {"video_sha256": receipt["video_sha256"],
                         "rgb_sequence_sha256": receipt["rgb_sequence_sha256"],
                         "frames": receipt["frames"]}
    if not diagnostic_fixture:
        review = json.loads((attempt / "pixel-review.json").read_text())
        if not review.get("reviewer") or review.get("reviewer", "").startswith("synthetic-"):
            raise ValueError("Independent original-camera pixel review required")
    return {"format": "worker-c412593-independent-source-audit", "case_id": case_id,
            "original_frames": count, "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "sealed_result_sha256": sha(attempt / "result.json"), "decoded_cameras": decoded,
            "software_audit_passed": True, "diagnostic_fixture": diagnostic_fixture,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--negative-missing-source", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.negative_missing_source:
        with tempfile.TemporaryDirectory(prefix="c412593-audit-negative-") as temp:
            root = Path(temp)
            for child in Path(args.attempt).iterdir():
                if child.name == "drive_history.jsonl":
                    continue
                (root / child.name).symlink_to(child.resolve(), target_is_directory=child.is_dir())
            result = audit(root, args.case, args.diagnostic_fixture)
    else:
        result = audit(args.attempt, args.case, args.diagnostic_fixture)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
