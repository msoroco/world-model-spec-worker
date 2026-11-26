"""Source-bound engineering range coverage; never a legal hazard classifier."""

import argparse
import hashlib
import json
from pathlib import Path

from saved_audit import audit_saved
from yield_view import CASES, require


MEASUREMENT_KEYS = {
    "ego_speed": "minimum_original_approach_speed_mps",
    "through_vehicle_center_station": "through_center_station_at_all_reference_m",
}
ASSIGNMENT = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def region(value, lower, upper):
    require(type(value) in (int, float) and type(lower) in (int, float) and
            type(upper) in (int, float) and lower < upper,
            "original engineering range value invalid")
    if value < lower:
        return "below"
    if value > upper:
        return "above"
    return "inside"


def audit_sweep(plan, evidence, repo, *, trusted_site_hashes):
    """Check original Native attempts against frozen numeric training ranges."""
    plan = json.loads(Path(plan).read_text()) if not isinstance(plan, dict) else plan
    evidence = json.loads(Path(evidence).read_text()) if not isinstance(evidence, list) else evidence
    root = Path(repo).resolve()
    require(isinstance(trusted_site_hashes, dict) and trusted_site_hashes,
            "independently reviewed site hash index missing")
    require(plan.get("assignment_id") == ASSIGNMENT,
            "wrong exact sweep assignment")
    ranges = plan.get("ranges")
    require(isinstance(ranges, list) and len(ranges) == 4 and
            {item.get("range_index") for item in ranges} == {0, 1, 2, 3},
            "four frozen judgment ranges required")
    claims = {}
    for item in evidence:
        require(isinstance(item, dict) and type(item.get("range_index")) is int and
                item.get("region") in ("below", "inside", "above") and
                item.get("attempt") and item.get("case_id") and
                item.get("expected_site_packet_sha256"),
                "source-bound sweep claim incomplete")
        key = (item["range_index"], item["region"])
        require(key not in claims, "duplicate exact sweep claim")
        claims[key] = item
    output = []
    for spec in ranges:
        ref = spec.get("source_ref", {})
        source = (root / ref.get("path", "")).resolve()
        require(source.is_relative_to(root) and source.is_file() and
                _sha(source) == ref.get("sha256"),
                "frozen judgment range source changed")
        variable = spec.get("variable")
        require(variable in MEASUREMENT_KEYS, "unsupported original sweep variable")
        index = spec["range_index"]
        required = ("inside", "above") if spec["planning_targets"]["below"] is None else (
            "below", "inside", "above")
        require(all((index, name) in claims for name in required),
                "original engineering sweep region missing")
        require((index, "below") not in claims or "below" in required,
                "impossible nonnegative below probe claimed")
        witnesses = []
        for name in required:
            claim = claims[(index, name)]
            case = next((candidate for candidate in CASES
                         if claim["case_id"] == ASSIGNMENT + "__" + candidate.case_id), None)
            require(case is not None, "unknown exact original sweep case")
            require(trusted_site_hashes.get(claim["case_id"]) ==
                    claim["expected_site_packet_sha256"],
                    "independently reviewed site hash differs")
            attempt = Path(claim["attempt"]).resolve()
            result = audit_saved(attempt, case,
                                 expected_site_packet_sha256=claim["expected_site_packet_sha256"])
            require(result["diagnostic_fixture"] is False,
                    "diagnostic sweep cannot establish original range")
            measured = json.loads((attempt / "measurement.json").read_text())
            value = measured.get(MEASUREMENT_KEYS[variable])
            require(region(value, spec["source_minimum"], spec["source_maximum"]) == name,
                    "original engineering sweep region differs")
            witnesses.append({"region": name, "case_id": claim["case_id"],
                              "native_seal_sha256": result["native_seal_sha256"],
                              "measured_value": value})
        output.append({"range_index": index, "variable": variable,
                       "frozen_source_sha256": ref["sha256"],
                       "witnesses": witnesses,
                       "legal_threshold_claimed": False})
    return {"format": "c157964-original-engineering-sweep-v1",
            "assignment_id": ASSIGNMENT,
            "ranges": output, "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--trusted-site-hashes", required=True,
                        help="independently reviewed exact-case site packet SHA-256 mapping")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    require(not target.exists(), "retain prior sweep audit")
    report = audit_sweep(args.plan, args.evidence, args.repo,
                         trusted_site_hashes=json.loads(Path(args.trusted_site_hashes).read_text()))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
