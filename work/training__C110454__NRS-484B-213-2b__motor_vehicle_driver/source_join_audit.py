"""Independent same-frame C110454 source join for saved delivery review.

Diagnostic mode checks source shapes only. Production mode requires retained
original Native provenance and a closed capture before any positive report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ("config.json", "native_samples.jsonl", "trace.jsonl",
           "capture/evidence.jsonl", "video_frames.jsonl", "acquisition-provenance.json")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite(values):
    return all(type(v) in (int, float) and math.isfinite(v) for v in values)


def audit(attempt: Path, processing_path: Path, case_id: str, candidate_id: str,
          construction_sha256: str, *, diagnostic: bool = False) -> dict:
    attempt, processing_path = attempt.resolve(), processing_path.resolve()
    require(case_id.startswith(HERE.name + "__"), "Wrong assignment case")
    require(all((attempt / name).is_file() for name in SOURCES), "Original source set incomplete")
    config, provenance, saved = (read(path) for path in
        (attempt / "config.json", attempt / "acquisition-provenance.json", processing_path))
    require(config.get("case_id") == case_id and config.get("candidate_id") == candidate_id and
            config.get("duration_s") == 24 and config.get("rate_hz") == 20,
            "Wrong exact case, candidate or capture interval")
    require(saved.get("format") == "worker-saved-processing" and
            saved.get("case_id") == case_id and saved.get("candidate_id") == candidate_id and
            saved.get("passed") is True and saved.get("recorded_only") is True and
            saved.get("originals_preserved") is True and saved.get("missing_evidence") is False and
            saved.get("native_revision", {}).get("construction_sha256") == construction_sha256,
            "Saved processing not bound to selected construction")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(saved.get("original_source_hashes", {}).get(name) == digest
                for name, digest in hashes.items()), "Saved source hash differs")
    if diagnostic:
        require(provenance.get("diagnostic_fixture") is True and
                provenance.get("provenance_kind") == "synthetic_fixture",
                "Diagnostic mode needs explicit synthetic provenance")
    else:
        require(provenance.get("diagnostic_fixture") is False and
                provenance.get("provenance_kind") == "native",
                "Synthetic source cannot establish original Native delivery")
        seal_path, exit_path = attempt / "capture-seal.json", attempt / "native-exit.json"
        require(seal_path.is_file() and exit_path.is_file(),
                "Original Native seal and exit required")
        seal, exit_record = read(seal_path), read(exit_path)
        require(seal.get("provenance_kind") == "native" and
                seal.get("diagnostic_fixture") is False and
                seal.get("frames") == 480 and
                exit_record.get("event") == "native_exit" and
                exit_record.get("native_process_exit_code") == 0 and
                exit_record.get("capture_seal_sha256") == sha(seal_path) and
                all(seal.get("sources", {}).get(name) == digest for name, digest in hashes.items()),
                "Original Native capture closure or source inventory differs")
    samples, trace, evidence, frames = (rows(attempt / name) for name in
        ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
         "video_frames.jsonl"))
    require(len(samples) == len(trace) == len(evidence) == len(frames) == 480,
            "Complete 480-frame original interval required")
    for index, (sample, movement, capture, frame) in enumerate(zip(samples, trace, evidence, frames)):
        ident, time = sample.get("native_frame"), sample.get("time_s")
        require(type(ident) is int and type(time) in (int, float) and math.isfinite(time) and
                frame.get("native_frame") == frame.get("carla_frame") ==
                movement.get("frame") == capture.get("original_frame") == ident and
                frame.get("video_frame") == sample.get("video_frame") == index and
                finite((frame.get("time_s"), movement.get("time_s"),
                        capture.get("recording_time_s"))) and
                all(abs(t - time) <= 1e-4 for t in
                    (frame["time_s"], movement["time_s"], capture["recording_time_s"])),
                "Original frame/time join differs")
        require(len(sample.get("body_xy_m", [])) == 4 and
                all(len(p) == 2 and finite(p) for p in sample["body_xy_m"]),
                "Original full-body footprint missing")
        body = capture.get("ego", {}).get("body_vertices_m", [])
        require(len(body) == 8 and all(len(v) >= 3 and finite(v[:3]) for v in body) and
                {(round(v[0], 5), round(v[1], 5)) for v in body} ==
                {(round(v[0], 5), round(v[1], 5)) for v in sample["body_xy_m"]},
                "Original body/capture vertices differ")
        center = sample.get("native_center_xy_m", [])
        pos = movement.get("position_m", [])
        ego_pos = capture["ego"].get("position_m", [])
        speed = sample.get("speed_m_s")
        require(len(center) == 2 and len(pos) >= 2 and len(ego_pos) >= 2 and
                finite((*center, *pos[:2], *ego_pos[:2], speed,
                        movement.get("speed_mps"), capture["ego"].get("speed_mps"))) and
                all(abs(center[j]-pos[j]) <= 1e-4 and abs(center[j]-ego_pos[j]) <= 1e-4
                    for j in (0, 1)) and
                abs(speed-movement["speed_mps"]) <= 1e-4 and
                abs(speed-capture["ego"]["speed_mps"]) <= 1e-4,
                "Original pose or speed differs")
        markers = (sample.get("speed_provenance"), movement.get("speed_provenance"),
                   capture["ego"].get("speed_provenance"))
        require(all(marker == "synthetic_native_sample" for marker in markers) if diagnostic else
                all(marker != "synthetic_native_sample" for marker in markers),
                "Synthetic speed cannot establish original Native motion")
    return {"format": "c110454-source-joined-delivery-v1", "case_id": case_id,
            "candidate_id": candidate_id, "construction_sha256": construction_sha256,
            "source_sha256": hashes, "saved_processing_sha256": sha(processing_path),
            "joined_frames": 480, "diagnostic_fixture": diagnostic,
            "original_native_sources_verified": not diagnostic,
            "source_join_passed": True, "passed": False,
            "complete_delivery_audit": False,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--construction-sha256", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.case, args.candidate,
                           args.construction_sha256, diagnostic=args.diagnostic), indent=2))
