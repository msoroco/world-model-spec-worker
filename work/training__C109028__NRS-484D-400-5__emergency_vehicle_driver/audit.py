"""Independent source-only comparison of emergency-call and ordinary-travel probes."""
import json
from pathlib import Path

from measure import measure, rows, sha


def audit(first, second):
    """Compare retained source tuples; no physical or legal verdict follows."""
    if len(first) != 4 or len(second) != 4:
        raise ValueError("Each case needs config, native, frame map and dispatch sources")
    a = measure(*first)
    b = measure(*second)
    ac = json.loads(Path(first[0]).read_text())
    bc = json.loads(Path(second[0]).read_text())
    if not ac["case_id"].endswith("__probe_a") or not bc["case_id"].endswith("__probe_b"):
        raise ValueError("Expected exact probe identities")
    fixed = ("assignment_id", "cell_id", "law_id", "actor", "frames", "rate_hz",
             "vehicle_actor_id", "other_vehicle_actor_id", "intersection_x_m", "camera_sources",
             "siren_requested", "warning_lamps_requested")
    if any(ac.get(key) != bc.get(key) for key in fixed):
        raise ValueError("Fixed construction policy differs")
    if ac.get("emergency_call_requested") is not True or bc.get("emergency_call_requested") is not False:
        raise ValueError("Requested authority contrast differs")
    an, bn = rows(first[1]), rows(second[1])
    am, bm = rows(first[2]), rows(second[2])
    ad, bd = rows(first[3]), rows(second[3])
    if an != bn or am != bm:
        raise ValueError("Matched native motion, signals or video joins differ")
    for x, y in zip(ad, bd):
        if {k: v for k, v in x.items() if k != "emergency_call_documented"} != \
                {k: v for k, v in y.items() if k != "emergency_call_documented"}:
            raise ValueError("Dispatch source fields other than call status differ")
    if not all(x.get("emergency_call_documented") is True for x in ad) or \
            not all(y.get("emergency_call_documented") is False for y in bd):
        raise ValueError("Documented emergency-call contrast differs")
    if not 0 < a["siren_observed_frames"] == b["siren_observed_frames"]:
        raise ValueError("Observed siren exposure differs")
    if a["siren_outside_documented_response_frames"] != 0 or \
            b["siren_outside_documented_response_frames"] != b["siren_observed_frames"]:
        raise ValueError("Observed siren versus documented response contrast differs")
    return {"format": "c109028-source-comparison-audit-v1", "passed": True,
            "case_ids": [a["case_id"], b["case_id"]], "frames_per_case": 600,
            "fixed_fields": list(fixed), "observed_siren_frames_each": a["siren_observed_frames"],
            "outside_documented_response_frames": [0, b["siren_observed_frames"]],
            "source_hashes": {"probe_a": [sha(p) for p in first],
                              "probe_b": [sha(p) for p in second]},
            "original_native_observed": False, "physical_legal_verdict": None}
