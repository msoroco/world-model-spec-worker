"""Synthetic source-packet tests for factual branches, without legal verdicts."""
from __future__ import annotations

import hashlib
import json
from restriction_measure import measure


BASE = {"source_kind": "synthetic_native_sample", "unladen_weight_lb": 8001,
        "weight_source_ref": "synthetic vehicle-weight document",
        "district": "residence", "truck_route": False,
        "route_source_ref": "synthetic road designation document",
        "civil_timestamp": "2026-11-23T20:00:00-08:00",
        "observed_speed_mps": 3.0, "written_permit_status": "absent"}


def run(**changes) -> dict:
    facts = dict(BASE, **changes)
    raw = json.dumps(facts, sort_keys=True).encode()
    return measure(raw, hashlib.sha256(raw).hexdigest())


def reject(reason: str, **changes) -> None:
    try:
        run(**changes)
    except ValueError as error:
        assert reason in str(error), (reason, error)
    else:
        raise AssertionError("invalid source accepted: " + reason)


def main() -> None:
    assert run()["night_window"] == "inside"
    assert run(civil_timestamp="2026-11-23T05:59:59-08:00")["night_window"] == "inside"
    assert run(civil_timestamp="2026-11-23T06:00:00-08:00")["night_window"] == "endpoint_unresolved"
    assert run(civil_timestamp="2026-11-23T06:00:01-08:00")["night_window"] == "outside"
    assert run(civil_timestamp="2026-11-23T18:59:59-08:00")["night_window"] == "outside"
    assert run(civil_timestamp="2026-11-23T19:00:00-08:00")["night_window"] == "endpoint_unresolved"
    assert run(civil_timestamp="2026-11-23T19:00:01-08:00")["night_window"] == "inside"
    assert run(unladen_weight_lb=8000)["vehicle_over_8000_lb"] is False
    assert run(unladen_weight_lb=8001)["vehicle_over_8000_lb"] is True
    assert run(truck_route=True)["non_truck_route"] is False
    assert run(truck_route=None)["non_truck_route"] is None
    assert run(district="unverified")["residence_district"] is None
    assert run(observed_speed_mps=0)["observed_movement"] is False
    assert run(written_permit_status="present")["permit_scope_and_conditions_verified"] is False
    reject("unladen weight provenance", weight_source_ref="")
    reject("truck-route authority", route_source_ref="")
    reject("UTC offset", civil_timestamp="2026-11-23T20:00:00")
    reject("original movement", observed_speed_mps=None)
    reject("written permit status", written_permit_status="invented")
    raw = json.dumps(BASE, sort_keys=True).encode()
    try:
        measure(raw, "0"*64)
    except ValueError as error:
        assert "hash mismatch" in str(error)
    else:
        raise AssertionError("source hash mismatch accepted")
    print(json.dumps({"format": "c394566-restriction-cpu-proof-v1", "passed": True,
                      "source_kind": "synthetic_native_sample", "time_probes": 7,
                      "weight_route_movement_permit_probes": 7, "negative_source_probes": 6,
                      "original_or_legal_result": None}, sort_keys=True))


if __name__ == "__main__":
    main()
