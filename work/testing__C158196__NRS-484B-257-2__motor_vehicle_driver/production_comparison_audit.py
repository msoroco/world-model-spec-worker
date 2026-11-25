"""Compare two independently accepted original C158196 deliveries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_case(value):
    return {key: item for key, item in value.items() if key != "case_id"}


def run(comparison_id, left, right, left_audit, right_audit):
    plan = read(ROOT / "case-plan.json")
    pair = next((item for item in plan["comparisons"]
                 if item["comparison_id"] == comparison_id), None)
    require(pair is not None and len(pair["case_ids"]) == 2,
            "unknown exact controlled comparison")
    attempts = (left.resolve(), right.resolve())
    audits = (read(left_audit), read(right_audit))
    for index in (0, 1):
        require(audits[index].get("case_id") == pair["case_ids"][index] and
                audits[index].get("capture_seal_sha256") ==
                sha(attempts[index] / "capture-seal.json") and
                audits[index].get("legal_verdict_claimed") is False and
                "independent_original_review" in audits[index].get("checks", []),
                "paired independent original delivery audit absent")
    sites = [read(root / "site.json") for root in attempts]
    devices = [read(root / "devices.json") for root in attempts]
    routes = [read(root / "routes.json") for root in attempts]
    histories = [read(root / "original-history.json") for root in attempts]
    require(sites[0] == sites[1], "paired original Native geometry or cameras differ")
    require(routes[0]["ego_approach"] == routes[1]["ego_approach"],
            "paired original ego route differs")
    require(routes[0]["counterpart_route"].get("road_id") ==
            routes[1]["counterpart_route"].get("road_id") and
            routes[0]["counterpart_route"].get("lane_id") ==
            routes[1]["counterpart_route"].get("lane_id") and
            routes[0]["counterpart_route"].get("vehicle_blueprint") ==
            routes[1]["counterpart_route"].get("vehicle_blueprint"),
            "paired counterpart route identity or vehicle differs")
    for root in attempts:
        config = read(root / "config.json")
        require(config.get("rate_hz") == 20 and config.get("duration_s") == 45 and
                len(config.get("cameras", [])) == 4,
                "paired Native recording policy differs")
    require(histories[0].get("case_id") == pair["case_ids"][0] and
            histories[1].get("case_id") == pair["case_ids"][1] and
            len(histories[0].get("frames", [])) ==
            len(histories[1].get("frames", [])) == 900,
            "paired exact original histories absent")
    if comparison_id == "approaching_spacing":
        require(devices[0]["control_context"] ==
                devices[1]["control_context"] == "stop_sign" and
                without_case(devices[0]) == without_case(devices[1]),
                "spacing pair changes original controlling authority")
        first = routes[0]["counterpart_route"]["native_waypoints"]
        second = routes[1]["counterpart_route"]["native_waypoints"]
        require(len(first) == len(second) and len(first) >= 2 and
                first[0] != second[0] and first[1:] == second[1:],
                "spacing pair must change only counterpart initial station")
    else:
        require(without_case(routes[0]) == without_case(routes[1]),
                "authority pair changes original routes")
        expected = {"within_stop_vs_yield": ("stop_sign", "yield_sign"),
                    "signal_exception_context": ("stop_sign", "signal_exception"),
                    "officer_exception_context": ("stop_sign", "officer_exception")}
        require((devices[0]["control_context"], devices[1]["control_context"]) ==
                expected[comparison_id], "authority pair lacks declared contrast")
    return {"comparison_id": comparison_id, "case_ids": pair["case_ids"],
            "original_site_sha256": [sha(root / "site.json") for root in attempts],
            "original_history_sha256": [sha(root / "original-history.json")
                                        for root in attempts],
            "delivery_audit_sha256": [sha(left_audit), sha(right_audit)],
            "fixed_conditions_checked": pair["fixed_conditions"],
            "deliberate_differences_checked": pair["deliberate_differences"],
            "immediate_hazard_legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--left-audit", type=Path, required=True)
    parser.add_argument("--right-audit", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.comparison_id, args.left, args.right,
                         args.left_audit, args.right_audit), sort_keys=True))
