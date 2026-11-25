"""Saved-only freight measurement; original source bytes are never rewritten."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_contract import audit_source_bundle, require_case_completion
from saved_delivery import CAMERAS, audit_delivery, probe_and_decode, sha256_file


def measure_freight_branch(attempt: Path, manifest: dict) -> dict:
    case_id = manifest["case_id"]
    variant = case_id.rsplit("__", 1)[-1]
    measured = audit_source_bundle(manifest, case_id=case_id, variant=variant,
                                   source_root=attempt, require_raw=True)
    return {"observed_action": measured["observed_action"],
            "commercial_status_reviewed": measured["commercial_status_reviewed"],
            "stopped_inside_zone": measured["stopped_inside_zone"],
            "inside_posted_window": measured["inside_posted_window"],
            "final_halt_duration_s": measured["final_halt_duration_s"],
            "legal_conclusion": "unresolved"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diagnostic(attempt: Path, manifest: dict, output: Path) -> dict:
    """Exercise sealed source measurement and Native/Core paths using synthetic bytes."""
    provenance_path = attempt / "fixture-provenance.json"
    if not provenance_path.is_file():
        raise ValueError("Missing required source: fixture-provenance.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if (manifest.get("acquisition_kind") != "synthetic_fixture" or
            manifest.get("diagnostic_fixture") is not True or
            provenance.get("diagnostic_fixture") is not True):
        raise ValueError("Diagnostic finalization requires explicit synthetic provenance")
    case_id = manifest["case_id"]
    variant = case_id.rsplit("__", 1)[-1]
    measured = audit_source_bundle(manifest, case_id=case_id, variant=variant,
                                   source_root=attempt, require_raw=True)
    require_case_completion(measured)
    media = manifest.get("media", {})
    if set(media) != set(CAMERAS):
        raise ValueError("Missing required source: four synthetic camera videos")
    for name, size in CAMERAS.items():
        ref = media[name]
        path = (attempt / ref["path"]).resolve(strict=True)
        if not path.is_relative_to(attempt) or sha256_file(path) != ref["sha256"]:
            raise ValueError("Synthetic camera seal differs: " + name)
        info = probe_and_decode(path)
        if (info.get("width"), info.get("height"), info.get("r_frame_rate"),
                str(info.get("nb_read_frames"))) != (*size, "20/1", "900"):
            raise ValueError("Synthetic camera profile differs: " + name)
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    recording = construction["recording_description"]
    rows = [json.loads(line) for line in (attempt / "freight_motion.jsonl").read_text().splitlines()]
    frame_map = [json.loads(line) for line in (attempt / "frame-map.jsonl").read_text().splitlines()]
    channels = {
        "ego_body_footprint": [{"min_station_m": row["ego_body_station_min_m"],
                                 "max_station_m": row["ego_body_station_max_m"]} for row in rows],
        "ego_speed": [row["ego_speed_mps"] for row in rows],
        "freight_activity": [{"cargo_actor_id": row["cargo_actor_id"],
                               "cargo_lateral_offset_m": row["cargo_lateral_offset_m"]} for row in rows],
        "posted_civil_time": [json.loads((attempt / manifest["sources"]["civil_time"]["path"])
                                         .read_text(encoding="utf-8"))["local_datetime"] for _ in rows],
        "camera_frame_map": frame_map,
    }
    channel_root = attempt / "channels"
    channel_root.mkdir(exist_ok=False)
    evidence = []
    for channel in recording["channels"]:
        name = channel["name"]
        path = channel_root / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": i / 20, "value": value}) + "\n"
                                for i, value in enumerate(channels[name])), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    for context in recording["context_inputs"]:
        name = context["name"]
        path = channel_root / (name + ".json")
        path.write_text(json.dumps({name: {"diagnostic_fixture": True,
                                          "source_manifest_sha256": sha(attempt / "freight-delivery-manifest.json")}}) + "\n")
        evidence.append({"name": name, "unit": context["unit"],
                         "reference": "channels/" + path.name})
    result = {
        "case_id": case_id,
        "measured_values": measured,
        "target_checks": [{"target": "synthetic_source_join", "requested": True,
                           "measured": True, "method": "sealed diagnostic source join",
                           "tolerance": 0, "matched": True,
                           "physical_cause_confirmed": False,
                           "cause_evidence": "synthetic fixture only"}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "900-frame synthetic software diagnostic",
        "physical_failure_flags": ["original physical outcome unverified"],
        "trace_reference": "trace.jsonl", "video_frame_map_reference": "video_frames.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "recording_description": recording, "recording_evidence": evidence,
        "realized_observables": {}, "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
    }
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    branch = {"observed_action": measured["observed_action"],
              "commercial_status_reviewed": measured["commercial_status_reviewed"],
              "stopped_inside_zone": measured["stopped_inside_zone"],
              "inside_posted_window": measured["inside_posted_window"],
              "final_halt_duration_s": measured["final_halt_duration_s"],
              "legal_conclusion": "unresolved"}
    report = {"format": "worker-freight-saved-analysis-v1", "case_id": case_id,
              "diagnostic_fixture": True, "physical_completion": False,
              "actual_pixels_reviewed": False,
              "measurements": {"freight_branch_observation": {
                  "value": branch, "method": "measure_freight_branch",
                  "sources": {name: sha(attempt / name) for name in
                              ("freight-delivery-manifest.json", "freight-native-source.json",
                               "freight_motion.jsonl")}}}}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def finalize(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    for name in ("freight-delivery-manifest.json", "freight-native-source.json",
                 "freight_motion.jsonl"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    manifest = json.loads((attempt / "freight-delivery-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("diagnostic_fixture") is True:
        return _diagnostic(attempt, manifest, Path(output))
    if manifest.get("acquisition_kind") != "original_native":
        raise ValueError("Original Native acquisition provenance required")
    measured = audit_delivery(manifest, attempt_root=attempt)
    branch = measure_freight_branch(attempt, manifest)
    source_names = ("freight-delivery-manifest.json", "freight-native-source.json",
                    "freight_motion.jsonl")
    report = {
        "format": "worker-freight-saved-analysis-v1",
        "case_id": measured["case_id"],
        "diagnostic_fixture": False,
        "physical_completion": measured["physical_case_completion"],
        "source_integrity": measured["source_integrity"],
        "full_video_decode": measured["full_video_decode"],
        "actual_pixels_reviewed": False,
        "legal_judgment": "unresolved_review",
        "measurements": {
            "freight_branch_observation": {
                "value": branch, "method": "measure_freight_branch",
                "sources": {name: sha(attempt / name) for name in source_names},
            },
            "freight_original_frames": {
                "value": measured["frames_checked"], "unit": "frames",
                "method": "sealed original Native motion and camera frame join",
                "reference": "freight_motion.jsonl",
            },
            "freight_physical_completion": {
                "value": measured["physical_case_completion"], "unit": "boolean",
                "method": "source-bound exact freight case completion check",
                "reference": "freight-native-source.json",
            },
        },
    }
    output = Path(output)
    if output.exists():
        raise ValueError("retain prior saved analysis; choose fresh output")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
