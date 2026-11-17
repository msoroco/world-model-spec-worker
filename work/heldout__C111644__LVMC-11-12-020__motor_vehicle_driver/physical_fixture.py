"""Exercise source-shaped turn completion and ordered saved lifecycle on CPU."""

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry_for(case, manifest):
    found = [e for e in read(manifest)["cases"] if e["case_id"] == case]
    require(len(found) == 1, "Unknown exact turn case")
    return found[0]


def physical(case, kind, manifest):
    require(kind in ("complete_motion", "incomplete_motion", "missing_evidence"),
            "Unknown physical fixture outcome")
    entry = entry_for(case, manifest)
    recipe = read(REPO / entry["fixture_recipe"])
    source = read(REPO / recipe["generator"]["source"])["files"]
    required = ("turn_indication_original.json", "turn_route_plan.json",
                "turn_body_original.jsonl", "trace.jsonl", "video_frames.jsonl")
    require(all(name in source for name in required), "Missing original-shaped turn source")
    hashes = {name: hashlib.sha256(source[name].encode()).hexdigest() for name in required}
    if kind == "missing_evidence":
        hashes.pop("turn_body_original.jsonl")
        status, observed = "unverified", {}
    else:
        body = [json.loads(line) for line in source["turn_body_original.jsonl"].splitlines()]
        trace = [json.loads(line) for line in source["trace.jsonl"].splitlines()]
        mapping = [json.loads(line) for line in source["video_frames.jsonl"].splitlines()]
        require(len(body) == len(trace) == len(mapping) >= 3,
                "Original turn physical fixture frame count differs")
        require(all(b["frame"] == t["frame"] == m["native_frame"]
                    and abs(b["time_s"] - t["time_s"]) < .005
                    and abs(b["time_s"] - m["time_s"]) < .005
                    for b, t, m in zip(body, trace, mapping)),
                "Original turn physical fixture frame join differs")
        centers = [b["subject"]["center_xy_m"] for b in body]
        headings = [b["subject"]["heading_deg"] for b in body]
        if kind == "incomplete_motion":
            centers = [centers[0]] * len(centers)
            headings = [headings[0]] * len(headings)
            hashes["turn_body_original.jsonl"] = hashlib.sha256(
                json.dumps({"synthetic_stalled_centers": centers,
                            "headings": headings}).encode()).hexdigest()
        path_m = sum(hypot(b[0]-a[0], b[1]-a[1])
                     for a, b in zip(centers, centers[1:]))
        angle_deg = abs((headings[-1] - headings[0] + 180) % 360 - 180)
        status = "met" if path_m >= 4 and 60 <= angle_deg <= 120 else "not_met"
        observed = {"sampled_body_path_m": path_m, "observed_heading_change_deg": angle_deg,
                    "first_frame": body[0]["frame"], "last_frame": body[-1]["frame"],
                    "engineering_criterion_not_legal": True}
    require(status == {"complete_motion": "met", "incomplete_motion": "not_met",
                       "missing_evidence": "unverified"}[kind],
            "Requested physical fixture outcome was not exercised")
    return {"case_id": case, "fixture_kind": kind, "diagnostic_fixture": True,
            "actual_native_capture": False, "provenance_kind": "native",
            "physical_checks": {"maneuver": {"status": status,
                "method": "source-joined original body path and 60-120 degree turn; 4 m engineering fixture criterion only",
                "sources": hashes,
                "missing_evidence": ["turn_body_original.jsonl"] if kind == "missing_evidence" else []}},
            "maneuver_completed": status == "met", "realized_observables": observed,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def lifecycle(case, manifest, attempt, owner):
    entry = entry_for(case, manifest)
    attempt, owner = Path(attempt), Path(owner)
    seal = read(attempt / "capture-seal.json")
    require(seal.get("diagnostic_fixture") is True and seal.get("frames", 0) >= 3
            and seal.get("restoration", {}).get("restored") is True
            and set(seal.get("encoder_exit_codes", {}))
            == {"overview", "approach", "reference_corner", "driver_reference"}
            and all(code == 0 for code in seal["encoder_exit_codes"].values()),
            "Capture closure, encoders or restoration incomplete")
    exit_receipt = read(attempt / "native-exit.json")
    require(exit_receipt.get("event") == "native_exit"
            and exit_receipt.get("capture_seal_sha256") == sha(attempt / "capture-seal.json")
            and exit_receipt.get("native_revision", {}).get("construction_sha256")
            == entry["construction_sha256"], "Native exit lacks sealed exact construction")
    release = read(owner)
    require(release.get("event") == "owner_released"
            and release.get("native_exit_sha256") == sha(attempt / "native-exit.json")
            and release.get("native_construction_sha256") == entry["construction_sha256"],
            "Owner release precedes or differs from Native exit")
    saved = read(HERE / entry["saved_processing"]["receipt"])
    require(saved.get("passed") is True and saved.get("recorded_only") is True
            and saved.get("originals_preserved") is True
            and saved.get("events", [None])[0] == "saved_processing_started",
            "Saved-only processing lacks ordered original preservation")
    return {"case_id": case, "diagnostic_fixture": True,
            "events": ["capture_finished", "encoders_closed", "restoration_verified",
                       "native_exit", "owner_released", "saved_processing_started"],
            "seal_sha256": sha(attempt / "capture-seal.json"),
            "native_exit_sha256": sha(attempt / "native-exit.json"),
            "owner_release_sha256": sha(owner),
            "saved_receipt_sha256": sha(HERE / entry["saved_processing"]["receipt"]),
            "actual_native_capture": False, "physical_acceptance_claimed": False}


def lifecycle_model(case, manifest, attempt):
    """Test a prospective closure sequence against retained diagnostic sources."""
    entry = entry_for(case, manifest)
    attempt = Path(attempt)
    source_names = ("turn_body_original.jsonl", "trace.jsonl", "video_frames.jsonl",
                    "overview.mkv", "approach.mkv", "reference_corner.mkv",
                    "driver_reference.mkv")
    require(all((attempt / name).is_file() for name in source_names),
            "Lifecycle model lacks complete original diagnostic sources")
    saved = read(HERE / entry["saved_processing"]["receipt"])
    require(saved.get("passed") is True and saved.get("recorded_only") is True
            and saved.get("originals_preserved") is True,
            "Lifecycle model lacks passing saved-only diagnostic proof")
    ordered = ("capture_finished", "encoders_closed", "restoration_verified",
               "native_exit", "owner_released", "saved_processing_started")

    def check(events):
        require(tuple(events) == ordered, "Saved processing precedes Native closure")

    check(ordered)
    rejected = False
    try:
        check((ordered[0], ordered[1], ordered[2], ordered[5], ordered[3], ordered[4]))
    except ValueError:
        rejected = True
    require(rejected, "Premature saved processing was not rejected")
    return {"case_id": case, "diagnostic_fixture": True,
            "order_model_only": True, "events": list(ordered),
            "rejected_premature_saved_processing": True,
            "original_source_sha256": {name: sha(attempt / name) for name in source_names},
            "saved_receipt_sha256": sha(HERE / entry["saved_processing"]["receipt"]),
            "actual_native_capture": False, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "provisional-manifest.json")
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--owner", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        result = lifecycle(args.case, args.manifest, args.attempt, args.owner)
    elif args.kind == "lifecycle_model":
        result = lifecycle_model(args.case, args.manifest, args.attempt)
    else:
        result = physical(args.case, args.kind, args.manifest)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.case, args.kind, json.dumps(result, sort_keys=True))
