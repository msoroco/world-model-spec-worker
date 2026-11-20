"""Independent fixed-condition check of three retained C10301 diagnostics.

This verifies source integrity and comparison isolation. Synthetic footage and
requested targets never establish physical speed or public-way status.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from speed_measurements import analyze

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
from worker_exchange.common import digest
from worker_exchange.media import audit as audit_video


SUFFIXES = ("source_verified_below_80", "source_verified_at_80",
            "source_verified_above_80")
SOURCES = ("subject_motion.jsonl", "video_frames.jsonl", "road_context.json",
           "trace.jsonl", "capture/evidence.jsonl", "overview.mkv", "approach.mkv",
           "reference_corner.mkv", "driver_reference.mkv")
FIXED_CONFIG = ("law_id", "cell_id", "actor", "duration_s", "fps", "rate_hz",
                "authored_scene_sha256", "cameras", "camera_transforms", "corridor_context")
FIXED_CONTEXT = ("native_map_id", "road_id", "lane_id", "route_source",
                 "alley_source", "access_aisle_source", "road_authority_source",
                 "subject_blueprint_id", "subject_actor_id")


def _read(path):
    return json.loads(path.read_text())


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_trace_dynamics(attempt):
    motion = [json.loads(line) for line in (attempt / 'subject_motion.jsonl').read_text().splitlines() if line.strip()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines() if line.strip()]
    if len(trace) != len(motion) or len(trace) < 2:
        raise ValueError('Incomplete original trace dynamics')
    previous = None
    for sample, row in zip(motion, trace):
        speed = sample.get('speed_mps')
        trace_speed = row.get('speed_mps')
        position = row.get('position_m')
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (speed, trace_speed)):
            raise ValueError('Original trace speed missing or nonfinite')
        if abs(speed - trace_speed) > 1e-6:
            raise ValueError('Original trace speed differs from motion')
        if not isinstance(position, list) or len(position) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in position):
            raise ValueError('Original trace position missing or nonfinite')
        if row.get('frame') != sample.get('frame') or row.get('time_s') != sample.get('time_s'):
            raise ValueError('Original trace frame join differs from motion')
        if previous is not None:
            prior_time, prior_speed, prior_position = previous
            expected = (prior_speed + speed) * (sample['time_s'] - prior_time) / 2
            if abs(math.dist(position, prior_position) - expected) > max(1.0, expected * .2):
                raise ValueError('Original trace displacement disagrees with sampled motion')
        previous = (sample['time_s'], speed, position)


def audit(attempts, compatibility_receipts):
    if len(attempts) != 3 or len(compatibility_receipts) != 3:
        raise ValueError("Exactly three attempt/compatibility pairs required")
    by_suffix = {}
    for attempt_path, receipt_path in zip(attempts, compatibility_receipts):
        attempt, receipt_path = Path(attempt_path), Path(receipt_path)
        config = _read(attempt / "config.json")
        context = _read(attempt / "road_context.json")
        receipt = _read(receipt_path)
        case_id = config["selected_case_id"]
        suffix = next((s for s in SUFFIXES if case_id.endswith("__" + s)), None)
        if suffix is None or suffix in by_suffix:
            raise ValueError("Missing, duplicate or foreign comparison case")
        if receipt.get("case_id") != case_id or receipt.get("candidate_id") != "primary" or receipt.get("passed") is not True:
            raise ValueError("Exact primary compatibility receipt differs")
        fixed_config = {}
        for key in FIXED_CONFIG:
            if key not in config:
                raise ValueError("Missing fixed config: " + key)
            fixed_config[key] = config[key]
        fixed_context = {}
        for key in FIXED_CONTEXT:
            if key not in context:
                raise ValueError("Missing fixed context: " + key)
            fixed_context[key] = context[key]
        hashes = {}
        decoded_video_hashes = {}
        for source in SOURCES:
            path = attempt / source
            if not path.is_file():
                raise ValueError("Missing source: " + source)
            hashes[source] = _sha(path)
            expected = receipt.get("fixture_manifest", {}).get(source)
            if source in ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
                provenance = _read(attempt / 'fixture-provenance.json')
                if (receipt.get('scope') != 'diagnostic software compatibility only' or
                        'CPU diagnostic only' not in provenance.get('scope', '')):
                    raise ValueError('Diagnostic comparison requires synthetic fixture provenance')
                frame_count = _read(attempt / 'capture/manifest.json')['frames']
                decoded = audit_video(path, frame_count)
                fingerprint = digest({'kind': 'generated-diagnostic-video',
                                      'frames': decoded['frames'],
                                      'dimensions': decoded['dimensions'],
                                      'fps': config['fps'],
                                      'rgb_sequence_sha256': decoded['rgb_sequence_sha256']})
                decoded_video_hashes[source] = fingerprint
                if expected != fingerprint:
                    raise ValueError("Compatibility decoded video differs: " + source)
            elif expected != hashes[source]:
                raise ValueError("Compatibility source hash differs: " + source)
        report = analyze(attempt)
        _check_trace_dynamics(attempt)
        if any(report["sources"][name] != hashes[name] for name in report["sources"]):
            raise ValueError("Measured original source hash differs")
        by_suffix[suffix] = {"case_id": case_id, "requested_speed_mph": config["requested_speed_mph"],
                             "sampled_peak_speed_mph": report["peak_sample"]["speed_mph"],
                             "sampled_peak_over_80": report["sampled_peak_greater_than_80_mph"],
                             "fixed_config": fixed_config, "fixed_context": fixed_context,
                             "source_sha256": hashes,
                             "decoded_video_fingerprint": decoded_video_hashes,
                             "compatibility_receipt_sha256": _sha(receipt_path)}
    if set(by_suffix) != set(SUFFIXES):
        raise ValueError("Missing comparison case")
    rows = [by_suffix[s] for s in SUFFIXES]
    if len({row["case_id"].rsplit("__", 1)[0] for row in rows}) != 1:
        raise ValueError("Mixed assignment comparison")
    for key in ("fixed_config", "fixed_context"):
        if any(row[key] != rows[0][key] for row in rows[1:]):
            raise ValueError("Fixed control condition changed: " + key)
    targets = [row["requested_speed_mph"] for row in rows]
    if not (targets[0] < 80 and targets[1] == 80 and targets[2] > 80):
        raise ValueError("Requested targets do not bracket 80 mph")
    measured = [row["sampled_peak_speed_mph"] for row in rows]
    return {"format": "worker-c10301-diagnostic-comparison", "comparison_id": "absolute_80_mph_boundary",
            "case_ids": [row["case_id"] for row in rows], "records": rows,
            "fixed_conditions_checked": list(FIXED_CONFIG) + list(FIXED_CONTEXT),
            "trace_dynamics_checked": True,
            "requested_targets_bracket_80": True,
            "measured_samples_bracket_80": measured[0] < 80 and measured[1] == 80 and measured[2] > 80,
            "physical_comparison_complete": False, "source_scope": "synthetic nine-frame diagnostic only",
            "between_sample_peak": "unresolved", "public_way_status": "unresolved",
            "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--compatibility", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = audit(args.attempt, args.compatibility)
    Path(args.output).write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print("Diagnostic comparison sources verified; requested bracket:",
          receipt["requested_targets_bracket_80"], "measured bracket:",
          receipt["measured_samples_bracket_80"])


if __name__ == "__main__":
    main()
