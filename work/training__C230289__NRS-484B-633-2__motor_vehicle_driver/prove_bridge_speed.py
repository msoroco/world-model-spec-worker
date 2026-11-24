"""Pinned-source synthetic CPU checks for the bridge speed diagnostic."""
import hashlib
import json
from pathlib import Path
from bridge_speed_measure import ASSIGNMENT, MPS_TO_MPH, measure

ASSIGNMENT_SHA = "aa1e318e420035325d18be17b81c4ec44c4c568995e143f1e1aa2f92bbf4a1fb"
WITNESS_SHA = "96ccc35f2f9ca4ecfb5c666f077208fe5cb88f2f693d326888a3a3af0a624a10"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sample(mph):
    maximum = 45.0
    admin = {"department_source_id": "synthetic-department",
             "investigation_source_id": "synthetic-investigation",
             "finding_source_id": "synthetic-finding",
             "declaration_source_id": "synthetic-declaration",
             "otherwise_permissible_speed_source_id": "synthetic-ordinary-limit",
             "safe_maximum_mph": maximum}
    signs = [{"end": end, "source_id": "synthetic-" + end,
              "department_authorization_source_id": "synthetic-authorization-" + end,
              "maintained_source_id": "synthetic-maintenance-" + end,
              "instruction_kind": "structure_maximum", "maximum_mph": maximum,
              "distance_before_end_ft": 100,
              "governed_approach_source_id": "synthetic-approach-" + end}
             for end in ("first", "second")]
    survey = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
              "fixed_cell": {"layout": "road", "maneuver": "travel", "control": "speed_limit_sign"},
              "highway_source_id": "synthetic-highway", "structure_source_id": "synthetic-bridge",
              "structure_type": "bridge", "chapter_408_source_id": "synthetic-chapter-408",
              "administrative_declaration": admin, "signs": signs}
    frames = [{"frame": i, "t_s": i / 20, "vehicle_id": "ego",
               "structure_id": "synthetic-bridge", "on_structure": 200 <= i < 400,
               "velocity_xyz_mps": [(mph / MPS_TO_MPH) if 250 <= i < 300 else 10.0, 0, 0],
               "requested_speed_mph": mph} for i in range(600)]
    trace = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
             "vehicle_id": "ego", "frames": frames}
    return survey, trace


def reject(survey, trace, expected):
    try:
        measure(enc(survey), enc(trace))
    except ValueError as exc:
        require(str(exc) == expected, "wrong rejection: " + str(exc))
        return
    raise ValueError("invalid source accepted")


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    require(hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA,
            "assignment source changed")
    require(hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA,
            "witness source changed")
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    require("bridge or other elevated structure" in law and "100 feet before each end" in law,
            "statutory structure/sign condition changed")
    above, trace = sample(55.0)
    p = measure(enc(above), enc(trace))
    require(p["structure_frames_above_declared_maximum"] == list(range(250, 300))
            and p["duration_s"] == 30 and not p["requested_speed_used"],
            "above-maximum or frame proof failed")
    below, trace = sample(35.0)
    q = measure(enc(below), enc(trace))
    require(q["structure_frames_above_declared_maximum"] == [], "below-maximum proof failed")
    below["signs"][1]["distance_before_end_ft"] = 95
    reject(below, trace, "structural sign placement or instruction missing")
    below, trace = sample(55.0)
    below["administrative_declaration"]["declaration_source_id"] = ""
    reject(below, trace, "structural maximum declaration provenance missing")
    below, trace = sample(55.0)
    trace["frames"][260]["velocity_xyz_mps"] = []
    reject(below, trace, "measured Native velocity missing")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA,
                      "witness_sha256": WITNESS_SHA, "above_survey_sha256": p["survey_sha256"],
                      "above_trace_sha256": p["trace_sha256"],
                      "below_survey_sha256": q["survey_sha256"],
                      "below_trace_sha256": q["trace_sha256"],
                      "checks": ["30s_20hz", "structure_occupancy_speed", "two_100ft_signs",
                                 "administrative_declaration", "native_velocity_source"]}, sort_keys=True))


if __name__ == "__main__":
    main()
