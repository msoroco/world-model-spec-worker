"""Pinned-source synthetic CPU checks for alley dwell and goods observations."""
import hashlib
import json
from pathlib import Path
from alley_dwell_measure import ASSIGNMENT, measure

ASSIGNMENT_SHA = "9403da615d8a0634526601f205cf715edf4e9cdfd99d3ea8f9fb410534c0a736"
WITNESS_SHA = "1900c0e356518fc1aa1a92ae97259c2fe7c464676b439adfd37d1a918c9d04b2"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sample(with_goods):
    context = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
               "fixed_cell": {"layout": "business_district_alley", "maneuver": "park",
                              "control": "alley_entrance"},
               "alley": {"boundary_source_id": "synthetic-boundary",
                         "highway_public_use_source_id": "synthetic-public",
                         "city_block_source_id": "synthetic-block",
                         "rear_property_service_source_id": "synthetic-rear",
                         "entrance_source_id": "synthetic-entrance",
                         "not_cul_de_sac_source_id": "synthetic-through"},
               "business_district": {"frontage_600ft_source_id": "synthetic-600",
                                     "frontage_300ft_source_id": "synthetic-300",
                                     "building_uses_source_id": "synthetic-uses"},
               "ordinance": {"authority_source_id": "synthetic-authority",
                             "jurisdiction_source_id": "synthetic-jurisdiction",
                             "applicability_source_id": "synthetic-applicability",
                             "status": "unknown"}}
    frames = [{"frame": i, "t_s": i / 20, "vehicle_id": "ego",
               "vehicle_speed_mps": 2.0 if i < 100 else 0.0,
               "within_alley": i >= 50,
               "alley_boundary_source_id": "synthetic-boundary",
               "goods_transfer_event_ids": ["synthetic-box-transfer"] if with_goods and i == 250 else []}
              for i in range(600)]
    return context, {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
                     "vehicle_id": "ego", "frames": frames}


def reject(context, trace, expected):
    try:
        measure(enc(context), enc(trace))
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
    require("business district" in law and "expeditious loading or unloading of goods" in law
            and "ordinance" in law, "statutory branches changed")
    context, trace = sample(True)
    goods = measure(enc(context), enc(trace))
    require(goods["observed_parked_alley_duration_s"] == 25
            and goods["observed_goods_event_ids"] == ["synthetic-box-transfer"]
            and goods["expeditiousness"] is None and goods["legal_result"] is None,
            "goods/dwell diagnostic failed")
    context, trace = sample(False)
    no_goods = measure(enc(context), enc(trace))
    require(no_goods["observed_goods_event_ids"] == [] and no_goods["legal_result"] is None,
            "no-goods diagnostic failed")
    context["ordinance"]["applicability_source_id"] = ""
    reject(context, trace, "local ordinance status source missing")
    context, trace = sample(False)
    context["business_district"]["frontage_300ft_source_id"] = ""
    reject(context, trace, "business district source missing")
    context, trace = sample(False)
    trace["frames"][250]["goods_transfer_event_ids"] = None
    reject(context, trace, "goods activity source missing")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA,
                      "witness_sha256": WITNESS_SHA,
                      "goods_trace_sha256": goods["trace_sha256"],
                      "no_goods_trace_sha256": no_goods["trace_sha256"],
                      "checks": ["30s_20hz", "alley_rest_duration", "goods_event_separation",
                                 "ordinance_source_rejection", "district_source_rejection",
                                 "goods_source_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
