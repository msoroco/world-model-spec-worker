"""Independent original rider, path-source and four-camera delivery audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import _original, required
from path_route import _inside, _point, _polygon
from source_deferred_runner import CAMERAS, FRAMES, _case_parts
from source_site import REQUIRED


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def decode_camera(path: Path, size: tuple[int, int]) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries",
                            "stream=nb_read_frames,width,height,r_frame_rate",
                            "-of", "json", str(path)], capture_output=True,
                           text=True, check=True, timeout=120)
    streams = json.loads(probe.stdout).get("streams", [])
    _require(len(streams) == 1, "one original camera stream required")
    stream = streams[0]
    _require(stream.get("nb_read_frames") == str(FRAMES) and
             stream.get("r_frame_rate") in ("20/1", "20") and
             (stream.get("width"), stream.get("height")) == size,
             "original camera profile or 900-frame count changed")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                    "-f", "null", "-"], capture_output=True, check=True, timeout=180)
    return {"decoded_frames": FRAMES, "width": size[0], "height": size[1]}


def audit_attempt(attempt: str | Path, processed: str | Path,
                  case_id: str, decoder=decode_camera) -> dict:
    attempt, processed = Path(attempt), Path(processed)
    _require(attempt.is_dir() and not attempt.is_symlink(), "original attempt missing")
    device, target, condition = _case_parts(case_id)
    site, rows, source_hashes = _original(attempt, case_id, device, target, condition)
    _require(len(rows) == FRAMES, "complete original rider history missing")
    roadway = _polygon(site["roadway_polygon"])
    path = _polygon(site["path_polygon"])
    for row in rows:
        corners = row.get("body_corners_xy")
        _require(isinstance(corners, list) and len(corners) >= 4,
                 "original rider body geometry missing")
        corners = [_point(point) for point in corners]
        _require(row["ego_body_on_roadway"] == any(_inside(point, roadway) for point in corners) and
                 row["ego_body_on_designated_path"] == any(_inside(point, path) for point in corners),
                 "original rider facility occupancy differs from body geometry")
    decoded = {}
    for name in CAMERAS:
        decoded[name] = decoder(required(attempt, name + ".mkv"),
                                (1920, 1080) if name == "overview" else (1280, 720))
        _require(decoded[name].get("decoded_frames") == FRAMES,
                 "original full camera decode missing: " + name)
    _require(processed.is_file() and not processed.is_symlink(),
             "processed original physical result missing")
    result = json.loads(processed.read_text())
    _require(result.get("case_id") == case_id and
             result.get("provenance_kind") == "native" and
             result.get("diagnostic_fixture") is False and
             result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met" and
             result.get("physical_acceptance_claimed") is False and
             result.get("legal_verdict_claimed") is False,
             "original physical completion and nonclaim result required")
    manifest = json.loads((attempt / "reviewed-site/source-manifest.json").read_text())
    fixed_sources = {name: manifest["sources"][name]["sha256"] for name in REQUIRED}
    fixed_sources["native_adapter"] = manifest["native_adapter_sha256"]
    return {"format": "c233829-original-delivery-audit-v1",
            "case_id": case_id, "device_type": device,
            "target_facility": target, "path_usability_context": condition,
            "map_id": site["map_id"], "roadway_id": site["roadway_id"],
            "path_id": site["path_id"],
            "route_waypoints": site["route_candidates"][target],
            "site_source_sha256": source_hashes["reviewed-site/site-context.json"],
            "capture_seal_sha256": source_hashes["capture-seal.json"],
            "processed_result_sha256": hashlib.sha256(processed.read_bytes()).hexdigest(),
            "fixed_sources": fixed_sources, "original_frame_count": FRAMES,
            "roadway_use_observed": any(row["ego_body_on_roadway"] for row in rows),
            "path_use_observed": any(row["ego_body_on_designated_path"] for row in rows),
            "camera_decodes": decoded, "physical_completion": True,
            "physical_visibility": "requires_independent_review",
            "path_usability_judgment": "requires_independent_review",
            "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior rider delivery audit")
    args.output.write_text(json.dumps(audit_attempt(args.attempt, args.processed,
                                                    args.case), indent=2) + "\n")


if __name__ == "__main__":
    main()
