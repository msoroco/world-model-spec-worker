"""Independent source and comparison audit of the C10365 CPU construction."""
import hashlib
import json
from pathlib import Path
import tempfile

from build import ASSIGNMENT_SHA, CASE, CASES, HERE, POLICIES, ROOT
from check import check
from prove_saved import fixture
from saved import process, read_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    assignment = ROOT / "inputs" / CASE.name / "assignment.json"
    plan = json.loads((CASE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "manifest.json").read_text())
    offline = json.loads((HERE / "offline-proof.json").read_text())
    saved = json.loads((HERE / "saved-proof.json").read_text())
    if sha(assignment) != ASSIGNMENT_SHA or len(manifest["entries"]) != 8 or \
            offline["positive_count"] != 8 or offline["negative_count"] != 32 or \
            saved["positive_count"] != 8 or saved["negative_count"] != 48:
        raise ValueError("Source or proof inventory differs")
    if plan["cases"][1]["target_type"] != "officer_exception_attempt":
        raise ValueError("Police exception falsely labeled as a violation")
    if len({json.dumps(v, sort_keys=True) for v in POLICIES.values()}) != 4:
        raise ValueError("Four constructions not distinct")
    policy_keys = ("assignment_sha256", "case_plan_sha256", "road_sha256",
                   "device_id", "device_station_x_m", "rider_blueprint", "rate_hz",
                   "frames", "officer_blueprint_filter")
    comparisons = []
    checked = []
    for candidate in POLICIES:
        left = HERE / "drafts" / "probe_a" / candidate
        right = HERE / "drafts" / "probe_b" / candidate
        ca, cb = json.loads((left / "config.json").read_text()), \
                 json.loads((right / "config.json").read_text())
        checked.extend((check(left), check(right)))
        if any(ca[k] != cb[k] for k in policy_keys) or \
                ca["officer_position_xy_m"] != cb["officer_position_xy_m"] or \
                ca["camera_policy"] != cb["camera_policy"] or \
                ca["requested_speed_mps"] != cb["requested_speed_mps"]:
            raise ValueError("Controlled pair changed fixed construction")
        if ca["officer_cue_requested"] != "no_contrary_direction" or \
                cb["officer_cue_requested"] != "proceed_request":
            raise ValueError("Controlled pair cue distinction absent")
        comparisons.append({"candidate": candidate, "fixed_keys": list(policy_keys),
                            "changed_request": "officer cue and bicycle response",
                            "legal_outcome": None})
    # Trigger measurements are taken by the saved processor, not by config labels.
    with tempfile.TemporaryDirectory() as tmp:
        raw, video, review = fixture(HERE / "drafts" / "probe_a" / "primary", Path(tmp))
        baseline = process(HERE / "drafts" / "probe_a" / "primary",
                           raw, video, review, synthetic=True)
        if any(baseline["fallback_triggers"].values()):
            raise ValueError("Baseline unexpectedly triggers a fallback")
        rows = read_rows(raw)
        for row in rows:
            if row["rider"]["speed_mps"] == 0:
                dx = 3.5
                row["rider"]["center_native_xyz_m"][0] += dx
                for vertex in row["rider"]["body_native_xyz_m"]:
                    vertex[0] += dx
        raw.write_text("".join(json.dumps(row) + "\n" for row in rows))
        from_margin = process(HERE / "drafts" / "probe_a" / "primary",
                              raw, video, review, synthetic=True)
        if from_margin["fallback_triggers"] != {
                "fallback1": True, "fallback2": False, "fallback3": False}:
            raise ValueError("Measured stop-margin fallback trigger")
        for row in rows:
            if row["rider"]["speed_mps"] == 0:
                row["rider"]["center_native_xyz_m"][0] -= 3.5
                for vertex in row["rider"]["body_native_xyz_m"]:
                    vertex[0] -= 3.5
        raw.write_text("".join(json.dumps(row) + "\n" for row in rows))
        visual = json.loads(review.read_text())
        visual["officer_cue_visibility"] = .8
        review.write_text(json.dumps(visual))
        from_visibility = process(HERE / "drafts" / "probe_a" / "primary",
                                  raw, video, review, synthetic=True)
        if from_visibility["fallback_triggers"] != {
                "fallback1": False, "fallback2": True, "fallback3": False}:
            raise ValueError("Measured visibility fallback trigger")
        raw3, video3, review3 = fixture(
            HERE / "drafts" / "probe_a" / "fallback3", Path(tmp))
        from_separation = process(HERE / "drafts" / "probe_a" / "fallback3",
                                  raw3, video3, review3, synthetic=True)
        if from_separation["fallback_triggers"] != {
                "fallback1": False, "fallback2": False, "fallback3": True}:
            raise ValueError("Measured separation fallback trigger")
    result = {
        "format": "c10365-independent-cpu-audit-v1",
        "assignment_sha256": sha(assignment), "checked_candidates": len(checked),
        "controlled_comparisons": comparisons,
        "measured_trigger_probes": {
            "baseline": baseline["fallback_triggers"],
            "stop_margin": {"margin_m": from_margin["stop_margin_m"],
                            "trigger": from_margin["fallback_triggers"]},
            "visibility": {"visibility": from_visibility["officer_cue_visibility"],
                           "trigger": from_visibility["fallback_triggers"]},
            "separation": {"distance_m": from_separation["min_officer_rider_separation_m"],
                           "trigger": from_separation["fallback_triggers"]}},
        "original_native_observed": False, "delivery_ready": False,
    }
    (HERE / "independent-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({"checked_candidates": result["checked_candidates"],
                      "controlled_pairs": len(result["controlled_comparisons"]),
                      "trigger_probes": len(result["measured_trigger_probes"])}))
