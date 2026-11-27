"""Exercise source-shaped rail crossing completion, failure, and lifecycle on CPU."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def source(suffix):
    spec = json.loads((HERE / ("diagnostic-" + suffix + ".json")).read_text())
    files = spec["files"]
    bodies = [json.loads(line) for line in files["rail-body.jsonl"].splitlines()]
    rays = [json.loads(line) for line in files["rail-rays.jsonl"].splitlines()]
    frames = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    return bodies, rays, frames, {name: hashlib.sha256(files[name].encode()).hexdigest()
                                   for name in ("rail-body.jsonl", "rail-rays.jsonl", "video_frames.jsonl")}


def fixture(suffix, kind):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown CPU physical fixture")
    bodies, rays, frames, hashes = source(suffix)
    if kind == "incomplete_motion":
        for body in bodies:
            for vertex in body["body_vertices_m"]:
                vertex[0] = min(vertex[0], -3.0)
    if kind == "missing_evidence":
        rays.pop(300)
    verified = (len(bodies) == len(rays) == len(frames) == 600 and
                all(body["frame"] == ray["frame"] == frame["native_frame"]
                    for body, ray, frame in zip(bodies, rays, frames)))
    crossed = verified and any(min(v[0] for v in body["body_vertices_m"]) <= 0 <=
                               max(v[0] for v in body["body_vertices_m"]) for body in bodies)
    moving = verified and (bodies[0]["body_vertices_m"][0][0] !=
                           bodies[-1]["body_vertices_m"][0][0])
    bilateral = verified and all(set(ray["directions"]) == {"left", "right"} for ray in rays)
    status = "unverified" if not verified else "met" if crossed and moving and bilateral else "not_met"
    return {"format": "lvmc-cpu-physical-fixture-v1", "case_id": HERE.name + "__selected_bd9b70e5__" + suffix,
            "kind": kind, "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "exact 600-frame synthetic body crossing-line and two-direction rail-ray join",
                "sources": [{"path": name, "sha256": digest} for name, digest in hashes.items()]}},
            "maneuver_completed": status == "met",
            "realized_observables": {"frame_count": 600, "crossing_line_overlap": crossed,
                                     "body_moved": moving, "bilateral_rays": bilateral}
                                    if status == "met" else {},
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        value = {"format": "lvmc-cpu-lifecycle-v1", "events": EVENTS,
                 "provenance_kind": "synthetic_fixture", "original_native_executed": False}
    else:
        value = fixture(args.condition, args.kind)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("CPU physical fixture status differs: " + args.kind)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "kind": args.kind, "condition": args.condition,
                      "physical_or_legal_acceptance": False}))


if __name__ == "__main__":
    main()
