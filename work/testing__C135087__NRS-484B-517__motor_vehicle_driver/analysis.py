"""Saved-only original stand observations; no statutory verdict is emitted."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stand import audit_saved_attempt
from stand_delivery import audit as audit_delivery


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _need(root, name):
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_designation(site, vehicles, attempt, rows, observed, media):
    return {"map_name": site["map_name"], "stand_kind": site["kind"],
            "designation_source": site["designation_source"], "sign_source": site["sign_source"],
            "sign_adequacy_judgment": None}


def measure_subject(site, vehicles, attempt, rows, observed, media):
    return {"actor_id": attempt["subject_id"], "class": vehicles["subject"]["kind"],
            "driver_identity_source": vehicles["subject"]["driver_identity_source"],
            "taxicab_use": vehicles["subject"]["compensated_taxicab_use"]}


def measure_entrant(site, vehicles, attempt, rows, observed, media):
    entrant = vehicles["entrant"]
    return {"actor_id": attempt["entrant_id"], "capacity_including_driver": entrant["design_capacity_including_driver"],
            "compensated_use_source": entrant["compensated_passenger_use_source"],
            "waiting_or_about_during_stop_frames": observed["entrant_waiting_or_about_during_stop_frames"]}


def measure_loading(site, vehicles, attempt, rows, observed, media):
    return {"stopped_frames": observed["stopped_frames"], "stop_duration_s": observed["stop_duration_s"],
            "loading_during_stop_frames": observed["loading_during_stop_frames"],
            "expedience_judgment": None}


def measure_access(site, vehicles, attempt, rows, observed, media):
    return {"access_obstructed_during_stop_frames": observed["access_obstructed_during_stop_frames"],
            "interference_judgment": None}


def measure_media(site, vehicles, attempt, rows, observed, media):
    return {"original_actor_frames": observed["source_frame_count"],
            "decoded_camera_frames": media["decoded_camera_frames"],
            "views": sorted(attempt["cameras"])}


ROWS = (("stand_designation", measure_designation), ("subject_classification", measure_subject),
        ("taxicab_entrant", measure_entrant), ("passenger_loading", measure_loading),
        ("access_effect", measure_access), ("original_four_view_media", measure_media))


def analyze(root):
    root = Path(root).resolve()
    config = json.loads(_need(root, "config.json").read_text())
    attempt = json.loads(_need(root, "attempt-source.json").read_text())
    site = json.loads(_need(root, "site-original.json").read_text())
    vehicles = json.loads(_need(root, "vehicle-original.json").read_text())
    if config["selected_case_id"] != attempt["case_id"]:
        raise ValueError("exact saved stand case changed")
    source = audit_saved_attempt(attempt, root)
    media = audit_delivery(root)
    rows = json.loads(_need(root, attempt["actor_rows"]["path"]).read_text())
    if len(rows) != 900 or media["decoded_camera_frames"] != 3600:
        raise ValueError("complete original stand history missing")
    measurements = source["measurement"]
    seals = {"attempt-source.json": sha(root / "attempt-source.json"),
             "site-original.json": sha(root / "site-original.json"),
             "vehicle-original.json": sha(root / "vehicle-original.json"),
             "actor-rows.json": attempt["actor_rows"]["sha256"],
             "frame-map.json": attempt["frame_map"]["sha256"],
             **{name + ".mkv": ref["sha256"] for name, ref in attempt["cameras"].items()}}
    report = {"format": "worker-analysis-report", "case_id": attempt["case_id"],
              "analysis_complete": True,
              "measurements": {key: {"method": method.__name__,
                                      "value": method(site, vehicles, attempt, rows, measurements, media),
                                      "sources": seals}
                               for key, method in ROWS},
              "provenance_kind": "native_original", "diagnostic_fixture": False,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
              "limitations": ["Stand designation, sign adequacy, temporary and expeditious loading, and interference need independent original review."]}
    channels = config["case"]["recording_description"]["channels"]
    if len(channels) != 5:
        raise ValueError("stand recording channel inventory changed")
    evidence = []
    for i, channel in enumerate(channels):
        name = f"stand-channel-{i}.jsonl"
        def value(row):
            if i == 0:
                return {"map_name": row["map_name"], "stand_source": "attempt-source.json"}
            if i == 1:
                return {"subject_id": row["subject_id"], "subject_speed_mps": row["subject_speed_mps"]}
            if i == 2:
                return {"entrant_id": row["entrant_id"], "entrant_speed_mps": row["entrant_speed_mps"]}
            if i == 3:
                return {key: row[key] for key in ("passenger_loading_active", "entrant_waiting",
                                                   "entrant_about_to_enter", "access_obstructed")}
            return {"frame": row["frame"], "cameras": sorted(attempt["cameras"])}
        (root / name).write_text("".join(json.dumps({"time_s": row["time_s"], "value": value(row)}) + "\n"
                                           for row in rows))
        evidence.append({"name": channel["name"], "unit": channel["unit"], "reference": name})
    context = config["case"]["recording_description"]["context_inputs"][0]
    (root / "stand-site-context.json").write_text(json.dumps(seals, indent=2) + "\n")
    evidence.append({"name": context["name"], "unit": context["unit"],
                     "reference": "stand-site-context.json"})
    from worker_exchange.native_output import write_result
    result = {"case_id": attempt["case_id"], "measured_values": measurements,
              "target_checks": [], "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "saved-only source measurement; original physical and legal review pending",
              "physical_failure_flags": ["physical_completion_unverified"],
              "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in attempt["cameras"]],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": "native_original", "diagnostic_fixture": False,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    write_result(root, result)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(report["case_id"])


if __name__ == "__main__":
    main()
