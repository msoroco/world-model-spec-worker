"""Source-bound diagnostic for a surveyed bridge maximum and measured crossing.

This reducer keeps administrative activation, bridge occupancy, and speed
separate. Synthetic packets test CPU behavior only; they are not evidence.
"""
import hashlib
import json
import math

ASSIGNMENT = "training__C230289__NRS-484B-633-2__motor_vehicle_driver"
MPS_TO_MPH = 2.2369362920544


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def measure(survey_bytes, trace_bytes):
    survey, trace = json.loads(survey_bytes), json.loads(trace_bytes)
    require(survey.get("assignment_id") == ASSIGNMENT and trace.get("assignment_id") == ASSIGNMENT,
            "assignment mismatch")
    require(survey.get("source_kind") == trace.get("source_kind")
            and survey.get("source_kind") in {"synthetic_native_sample", "original_native_observation"},
            "source kind mismatch")
    require(survey.get("fixed_cell") == {"layout": "road", "maneuver": "travel",
                                          "control": "speed_limit_sign"}, "fixed cell mismatch")
    require(survey.get("highway_source_id") and survey.get("structure_source_id")
            and survey.get("structure_type") in {"bridge", "other_elevated_structure"}
            and survey.get("chapter_408_source_id"), "highway structure provenance missing")
    admin = survey.get("administrative_declaration", {})
    require(admin.get("department_source_id") and admin.get("investigation_source_id")
            and admin.get("finding_source_id") and admin.get("declaration_source_id")
            and admin.get("otherwise_permissible_speed_source_id"),
            "structural maximum declaration provenance missing")
    maximum = admin.get("safe_maximum_mph")
    require(isinstance(maximum, (int, float)) and math.isfinite(maximum) and maximum > 0,
            "declared structural maximum missing")
    signs = survey.get("signs", [])
    require(len(signs) == 2 and {s.get("end") for s in signs} == {"first", "second"},
            "both structure-end signs required")
    require(all(s.get("source_id") and s.get("department_authorization_source_id")
                and s.get("maintained_source_id") and s.get("instruction_kind") == "structure_maximum"
                and s.get("maximum_mph") == maximum and s.get("distance_before_end_ft") == 100
                and s.get("governed_approach_source_id") for s in signs),
            "structural sign placement or instruction missing")
    frames = trace.get("frames", [])
    require(len(frames) >= 600 and all(f.get("frame") == i
            and abs(f.get("t_s", -1) - i / 20) < 1e-8 for i, f in enumerate(frames)),
            "30-second contiguous 20 Hz recording required")
    require(trace.get("vehicle_id") and all(f.get("vehicle_id") == trace["vehicle_id"] for f in frames),
            "vehicle identity changed")
    require(all(f.get("structure_id") == survey["structure_source_id"]
                and isinstance(f.get("on_structure"), bool) for f in frames),
            "structure occupancy source missing")
    require(all(isinstance(f.get("velocity_xyz_mps"), list)
                and len(f["velocity_xyz_mps"]) == 3
                and all(isinstance(v, (int, float)) and math.isfinite(v)
                        for v in f["velocity_xyz_mps"]) for f in frames),
            "measured Native velocity missing")
    occupied = [f for f in frames if f["on_structure"]]
    require(occupied, "no observed structure occupancy")
    speeds = [math.sqrt(sum(v * v for v in f["velocity_xyz_mps"])) * MPS_TO_MPH for f in occupied]
    above = [f["frame"] for f, mph in zip(occupied, speeds) if mph > maximum]
    return {"format": "c230289-bridge-speed-diagnostic-v1", "assignment_id": ASSIGNMENT,
            "source_kind": survey["source_kind"], "survey_sha256": digest(survey_bytes),
            "trace_sha256": digest(trace_bytes), "frame_count": len(frames),
            "duration_s": len(frames) / 20, "structure_frame_range": [occupied[0]["frame"],
                                                                  occupied[-1]["frame"]],
            "declared_maximum_mph": maximum, "max_observed_structure_speed_mph": max(speeds),
            "structure_frames_above_declared_maximum": above,
            "requested_speed_used": False, "legal_result": None,
            "physical_completion": False,
            "unresolved": ["original geometry and signs", "administrative provenance",
                           "physical measured vehicle crossing"]}
