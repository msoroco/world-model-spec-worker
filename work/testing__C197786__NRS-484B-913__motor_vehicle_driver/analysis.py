"""Selected saved-only hose measurement from source-bound Native rows."""

import argparse
import json
from pathlib import Path

from delivery_audit import verify_native_frames, verify_original_context, verify_sources
from fire_hose_delivery import body_over_hose_frames, inspect_saved_hose


def measure_hose_passage(stage):
    root = Path(stage)
    for name in ("original-context/private_way.json", "original-context/hose.json",
                 "original-context/incident.json", "original-context/official.json",
                 "original-context/consent.json", "original-context/vehicle.json",
                 "frames.jsonl", "seal.json"):
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    path = root / "saved-packet.json"
    if not path.is_file():
        raise ValueError("Missing required source: saved-packet.json")
    packet = json.loads(path.read_text())
    verify_sources(packet, root)
    verify_native_frames(packet, root)
    verify_original_context(packet, root)
    observed = inspect_saved_hose(packet, packet["case_id"])
    contact = body_over_hose_frames(packet, packet["case_id"])
    sources = {packet[key]["source_path"]: packet[key]["sha256"] for key in
               ("hose", "road", "incident", "command_official", "consent", "vehicle")}
    sources.update({"saved-packet.json": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                    "frames.jsonl": packet["native"]["source_sha256"]})
    return {"method": "measure_hose_passage", "sources": sources,
            "value": {"case_id": packet["case_id"], "body_contact_frames": contact,
                      "centerline_crossing_frames": observed["crossing_frames"],
                      "hose_protection": observed["hose_protection"],
                      "incident_purpose": observed["incident_purpose"],
                      "consent_status": observed["consent_status"],
                      "command_official": observed["official_identity"],
                      "legal_judgment": None}}


def analyze(stage, output, *, report_only=False):
    root = Path(stage)
    measurement = measure_hose_passage(root)
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    cid = config["selected_case_id"]
    if measurement["value"]["case_id"] != cid:
        raise ValueError("selected case differs from saved original source")
    expect = config["case"]["planned_hose_crossing"]
    if bool(measurement["value"]["body_contact_frames"]) != expect:
        raise ValueError("actual saved body passage differs from exact case")
    report = {"format": "worker-analysis-report", "case_id": cid,
              "measurements": {"hose_passage_history": measurement},
              "legal_judgment": None,
              "limitations": ["Physical and legal acceptance require independent original review."]}
    if not report_only:
        description = construction["recording_description"]
        packet = json.loads((root / "saved-packet.json").read_text())
        channel_root = root / "channels"
        channel_root.mkdir(exist_ok=False)
        channels = {
            "original_ego_body_footprint": lambda r: r["ego_body_corners_xy"],
            "actual_hose_segment": lambda r: packet["hose"]["segment_xy"],
            "hose_protection": lambda r: packet["hose"]["protection"],
            "incident_purpose": lambda r: packet["incident"]["purpose"],
            "command_official": lambda r: packet["command_official"]["identity"],
            "consent_source": lambda r: packet["consent"],
            "private_way_access": lambda r: packet["road"].get("permitted_access"),
        }
        evidence = []
        for channel in description["channels"]:
            name = channel["name"]
            if name not in channels:
                raise ValueError("selected channel lacks original projection: " + name)
            target = channel_root / (name + ".jsonl")
            with target.open("x") as stream:
                for row in packet["native"]["frames"]:
                    stream.write(json.dumps({"time_s": row["elapsed_seconds"],
                                             "value": channels[name](row)}) + "\n")
            evidence.append({"name": name, "unit": channel["unit"],
                             "reference": str(target.relative_to(root))})
        contexts = {"reviewed_original_site": {"road": packet["road"], "hose": packet["hose"]}}
        for item in description["context_inputs"]:
            name = item["name"]
            if name not in contexts:
                raise ValueError("selected context lacks original projection: " + name)
            target = channel_root / (name + ".json")
            target.write_text(json.dumps({name: contexts[name]}) + "\n")
            evidence.append({"name": name, "unit": item["unit"],
                             "reference": str(target.relative_to(root))})
        target = {"target": "original body over actual hose", "requested": expect,
                  "measured": bool(measurement["value"]["body_contact_frames"]),
                  "method": "measure_hose_passage", "tolerance": 0, "matched": True,
                  "physical_cause_confirmed": False,
                  "cause_evidence": measurement["sources"]}
        result = {"case_id": cid, "measured_values": measurement["value"],
                  "target_checks": [target], "setup_confirmed": False,
                  "behavior_attempted": False, "maneuver_completed": False,
                  "termination_reason": "Saved source measurement only; physical review pending",
                  "physical_failure_flags": [], "trace_reference": "trace.jsonl",
                  "video_references": [v + ".mkv" for v in
                                       ("overview", "approach", "reference_corner", "driver_reference")],
                  "video_frame_map_reference": "video_frames.jsonl",
                  "recording_description": description, "recording_evidence": evidence,
                  "realized_observables": {}, "legal_judgment": None}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    print(analyze(args.attempt, args.output, report_only=args.report_only)["case_id"])


if __name__ == "__main__":
    main()
