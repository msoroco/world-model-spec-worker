"""Independent C10307 saved delivery audit; never decides legal prudence.

A positive local review must bind the exact result and four original camera
files. CPU fixture tests can exercise rejection, not establish physical truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from saved_delivery import CAMERAS, audit_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("delivery source missing or outside attempt: " + str(relative))
    return path


def audit_delivery(attempt: Path, case_id: str, review_path: Path) -> dict:
    attempt = Path(attempt).resolve()
    native_path = _inside(attempt, "result.json")
    native = json.loads(native_path.read_text())
    if native.get("case_id") != case_id or native.get("diagnostic_fixture") is True:
        raise ValueError("delivery needs exact non-diagnostic Native result")
    saved = audit_saved(attempt, case_id)
    trace_path = _inside(attempt, native.get("trace_reference", ""))
    map_path = _inside(attempt, native.get("video_frame_map_reference", ""))
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    mapping = [json.loads(line) for line in map_path.read_text().splitlines()]
    if len(trace) != saved["frame_count"] or len(mapping) != len(trace):
        raise ValueError("delivery trace, media and original frame counts differ")
    if any((row.get("video_frame") != index or row.get("carla_frame") != trace[index].get("frame")
            or row.get("time_s") != trace[index].get("time_s")) for index, row in enumerate(mapping)):
        raise ValueError("delivery original frame map differs from trace")
    cameras = {name: saved["cameras"][name]["sha256"] for name in CAMERAS}
    if set(native.get("video_references", [])) != {name + ".mkv" for name in CAMERAS}:
        raise ValueError("delivery Native result omits original cameras")
    review_path = Path(review_path)
    review = json.loads(review_path.read_text())
    if (review.get("format") != "c10307-independent-physical-review-v1" or
            review.get("case_id") != case_id or review.get("native_result_sha256") != sha(native_path) or
            review.get("video_frame_map_sha256") != sha(map_path) or
            review.get("videos") != cameras):
        raise ValueError("independent pixel review is absent or stale")
    checks = review.get("checks", {})
    needed = ("actual_bicycle_pixels", "rack_visible", "human_powered_bicycle_classification",
              "municipal_jurisdiction", "physical_route_completion", "full_episode_coverage")
    if any(checks.get(key) is not True for key in needed) or not review.get("reviewer") or not review.get("review_source"):
        raise ValueError("independent physical review lacks required positive checks")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "passed": True, "scope": "physical source review and media integrity; legal prudence unresolved",
            "native_result_sha256": sha(native_path), "review_sha256": sha(review_path),
            "frame_count": len(trace), "trace_sha256": sha(trace_path),
            "video_frame_map_sha256": sha(map_path), "video_sha256": cameras,
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "legal_prudence": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite delivery audit")
    receipt = audit_delivery(args.attempt, args.case, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
