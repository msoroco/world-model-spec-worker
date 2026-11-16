"""Exercise complete, incomplete and missing original turn motion on CPU sources."""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def rows(source):
    return [json.loads(line) for line in source.splitlines() if line.strip()]


def run(case, kind, manifest_name="provisional-manifest.json"):
    manifest = json.loads((HERE / manifest_name).read_text())
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    if entry is None or kind not in KINDS:
        raise ValueError("Unknown exact turn physical fixture")
    recipe = json.loads((ROOT / entry["fixture_recipe"]).read_text())
    files = json.loads((ROOT / recipe["generator"]["source"]).read_text())["files"]
    required = ("route_survey_original.json", "route_survey_capture_receipt.json",
                "body_corners_original.jsonl", "video_frames.jsonl", "trace.jsonl")
    if any(name not in files for name in required):
        raise ValueError("Diagnostic original turn inventory incomplete")
    sources = {name: sha256(files[name].encode()).hexdigest() for name in required}
    if kind == "missing_evidence":
        sources.pop("body_corners_original.jsonl")
        status, observed = "unverified", {}
    else:
        survey = json.loads(files["route_survey_original.json"])
        receipt = json.loads(files["route_survey_capture_receipt.json"])
        if (receipt.get("case_id") != case or receipt.get("source_sha256") != sources["route_survey_original.json"]
                or survey.get("approach_directions") != 2 or survey.get("destination_directions") != 1):
            raise ValueError("Original turn site source/receipt differs")
        body = rows(files["body_corners_original.jsonl"])
        mapping = rows(files["video_frames.jsonl"])
        trace = rows(files["trace.jsonl"])
        if not len(body) == len(mapping) == len(trace) or len(body) < 3:
            raise ValueError("Original turn motion inventory incomplete")
        identities = [(row["frame"], row["time_s"]) for row in body]
        if (identities != [(row["carla_frame"], row["time_s"]) for row in mapping]
                or identities != [(row["frame"], row["time_s"]) for row in trace]
                or {row["phase"] for row in body} != {"approach", "entry", "departure"}):
            raise ValueError("Original turn frame/phase join differs")
        centers = [[sum(corner[i] for corner in row["body_corners_xy_m"]) / 4
                    for i in (0, 1)] for row in body]
        if kind == "incomplete_motion":
            centers = [centers[0] for _ in centers]
            sources["body_corners_original.jsonl"] = sha256(json.dumps(centers).encode()).hexdigest()
        path_m = sum(hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(centers, centers[1:]))
        displacement_m = hypot(centers[-1][0]-centers[0][0], centers[-1][1]-centers[0][1])
        status = "met" if path_m > 4 and displacement_m > 4 else "not_met"
        observed = {"first_frame": identities[0][0], "last_frame": identities[-1][0],
                    "body_path_m": path_m, "body_displacement_m": displacement_m,
                    "engineering_criterion_not_legal": True}
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if status != expected:
        raise ValueError("Turn fixture did not exercise requested outcome")
    return {"case_id": case, "fixture_kind": kind, "diagnostic_fixture": True,
            "actual_native_capture": False, "provenance_kind": "native",
            "physical_checks": {"maneuver": {"status": status,
                "method": "joined original-shaped full-body turn path; 4 m engineering fixture criterion only",
                "sources": sources,
                "missing_evidence": ["body_corners_original.jsonl"] if kind == "missing_evidence" else []}},
            "maneuver_completed": status == "met", "realized_observables": observed,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--manifest-name", default="provisional-manifest.json")
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.manifest_name), indent=2))
