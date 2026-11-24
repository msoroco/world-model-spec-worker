"""Source-bound diagnostic of alley occupancy, dwell and goods activity.

No numeric definition of expeditiousness or ordinance outcome is inferred.
"""
import hashlib
import json
import math

ASSIGNMENT = "training__C378809__NRS-484B-477-1a__motor_vehicle_driver"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def measure(context_bytes, trace_bytes):
    context, trace = json.loads(context_bytes), json.loads(trace_bytes)
    require(context.get("assignment_id") == ASSIGNMENT and trace.get("assignment_id") == ASSIGNMENT,
            "assignment mismatch")
    require(context.get("source_kind") == trace.get("source_kind")
            and context.get("source_kind") in {"synthetic_native_sample", "original_native_observation"},
            "source kind mismatch")
    require(context.get("fixed_cell") == {"layout": "business_district_alley", "maneuver": "park",
                                           "control": "alley_entrance"}, "fixed cell mismatch")
    alley = context.get("alley", {})
    require(all(alley.get(k) for k in ("boundary_source_id", "highway_public_use_source_id",
                                          "city_block_source_id", "rear_property_service_source_id",
                                          "entrance_source_id", "not_cul_de_sac_source_id")),
            "statutory alley or entrance source missing")
    district = context.get("business_district", {})
    require(district.get("frontage_600ft_source_id") and district.get("frontage_300ft_source_id")
            and district.get("building_uses_source_id"), "business district source missing")
    ordinance = context.get("ordinance", {})
    require(ordinance.get("authority_source_id") and ordinance.get("jurisdiction_source_id")
            and ordinance.get("applicability_source_id")
            and ordinance.get("status") in {"none_applicable", "applicable_otherwise", "unknown"},
            "local ordinance status source missing")
    frames = trace.get("frames", [])
    require(len(frames) >= 600 and all(f.get("frame") == i
            and abs(f.get("t_s", -1) - i / 20) < 1e-8 for i, f in enumerate(frames)),
            "30-second contiguous 20 Hz trace required")
    require(trace.get("vehicle_id") and all(f.get("vehicle_id") == trace["vehicle_id"] for f in frames),
            "vehicle identity changed")
    require(all(isinstance(f.get("vehicle_speed_mps"), (int, float))
                and math.isfinite(f["vehicle_speed_mps"]) and f["vehicle_speed_mps"] >= 0
                and isinstance(f.get("within_alley"), bool)
                and f.get("alley_boundary_source_id") == alley["boundary_source_id"]
                for f in frames), "saved position or velocity source missing")
    require(all(isinstance(f.get("goods_transfer_event_ids"), list)
                and all(isinstance(g, str) and g for g in f["goods_transfer_event_ids"])
                for f in frames), "goods activity source missing")
    # Sensor rest tolerance only; never a statutory definition of parking.
    parked = [f for f in frames if f["within_alley"] and f["vehicle_speed_mps"] <= 0.05]
    require(parked, "no observed alley stop")
    event_ids = sorted({g for f in parked for g in f["goods_transfer_event_ids"]})
    return {"format": "c378809-alley-dwell-diagnostic-v1", "assignment_id": ASSIGNMENT,
            "context_sha256": hashlib.sha256(context_bytes).hexdigest(),
            "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
            "source_kind": context["source_kind"], "frame_count": len(frames),
            "duration_s": len(frames) / 20, "parked_alley_frame_range": [parked[0]["frame"],
                                                                  parked[-1]["frame"]],
            "observed_parked_alley_duration_s": len(parked) / 20,
            "rest_measurement_tolerance_mps": 0.05,
            "observed_goods_event_ids": event_ids,
            "ordinance_status": ordinance["status"],
            "expeditiousness": None, "legal_result": None,
            "physical_completion": False,
            "unresolved": ["actual goods transfer purpose and continuity",
                           "expeditious character", "ordinance interpretation"]}
