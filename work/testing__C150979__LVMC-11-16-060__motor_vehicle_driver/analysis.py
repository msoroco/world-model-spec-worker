"""Saved-only source-bound speed and posting measurement; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import speed_delivery as speed

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    construction = json.loads(_required(root, "construction.json").read_text())
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id or not case_id.startswith(speed.ASSIGNMENT + "__"):
        raise ValueError("selected construction case differs")
    inventory = json.loads(_required(root, "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native inventory case mismatch")
    sources = inventory.get("sources", {})
    expected_paths = {"site": "site.json", "history": "history.json", "frame_map": "frame-map.json"}
    for name, filename in expected_paths.items():
        source = sources.get(name, {})
        if source.get("path") != filename or source.get("sha256") != _sha(_required(root, filename)):
            raise ValueError("source hash mismatch: " + filename)
    site = json.loads((root / "site.json").read_text())
    frames = json.loads((root / "history.json").read_text())
    frame_map = json.loads((root / "frame-map.json").read_text())
    fixture = (root / "fixture-provenance.json").is_file()
    expected = 9 if fixture else 900
    if inventory.get("frame_count") != expected or len(frames) != expected or len(frame_map) != expected:
        raise ValueError("original speed frame count incomplete")
    if inventory.get("camera_views") != list(VIEWS):
        raise ValueError("four-view Native inventory incomplete")
    for index, (row, mapping) in enumerate(zip(frames, frame_map)):
        if mapping != {"frame_index": index, "native_frame": row.get("source_frame_id"),
                       "time_s": row.get("time_s")}:
            raise ValueError("original frame map join mismatch")
    return speed.measure(site, case_id.removeprefix(speed.ASSIGNMENT + "__"),
                         site["map_sha256"], frames, diagnostic_fixture=fixture)


def analyze(attempt, output):
    root = Path(attempt)
    observed = measure(root)
    construction = json.loads(_required(root, "construction.json").read_text())
    trace = [json.loads(line) for line in _required(root, "trace.jsonl").read_text().splitlines()]
    if len(trace) != observed["original_frame_count"]:
        raise ValueError("original trace count incomplete")
    hashes = {name: _sha(_required(root, name)) for name in ("site.json", "history.json", "frame-map.json")}
    measurements = {"observed_speed_mph_min": observed["observed_speed_mph_min"],
                    "observed_speed_mph_max": observed["observed_speed_mph_max"],
                    "posting_context": observed["posting_context"],
                    "original_frame_count": observed["original_frame_count"]}
    report = {"format": "worker-analysis-report", "case_id": observed["case_id"],
              "measurements": {"observed_speed": {"method": "measure",
                                                   "value": measurements, "sources": hashes}},
              "diagnostic_fixture": (root / "fixture-provenance.json").is_file(),
              "legal_verdict_claimed": False,
              "limitations": ["Prima facie effect and Title posting authority require local review.",
                              "CPU fixtures do not establish physical Native success."]}
    description = construction["recording_description"]
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    values = {
        "observed_speed_mph": {"source_sha256": hashes["history.json"],
                               "range_mph": [observed["observed_speed_mph_min"], observed["observed_speed_mph_max"]]},
        "governing_posting_context": {"source_sha256": hashes["site.json"],
                                       "posting_context": observed["posting_context"],
                                       "legal_applicability": "unresolved"},
        "original_ego_speed": {"source_sha256": hashes["history.json"],
                               "range_mph": [observed["observed_speed_mph_min"], observed["observed_speed_mph_max"]]},
        "original_route_station": {"source_sha256": hashes["history.json"],
                                   "governed_samples": len(observed["governed_original_samples"])},
        "original_sign_inventory": {"source_sha256": hashes["site.json"],
                                    "posting_context": observed["posting_context"]},
        "original_four_camera_pixels": {"source_sha256": _sha(_required(root, "video_frames.jsonl")),
                                        "view_count": 4}}
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unexpected speed source channel: " + name)
        target = channels / (name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"], "value": values[name]}) + "\n"
                                  for row in trace))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    context = channels / "reviewed_speed_site.json"
    context.write_text(json.dumps({"reviewed_speed_site": {
        "site_sha256": hashes["site.json"], "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_speed_site", "unit": "source",
                     "reference": str(context.relative_to(root))})
    result = {"case_id": observed["case_id"], "measured_values": measurements,
              "target_checks": [{"target": "source-bound observed speed and posting",
                                 "requested": observed["target_mph"], "measured": measurements,
                                 "method": "speed_delivery.measure", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "legal_judgment": None,
              "physical_acceptance_claimed": False}
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()
