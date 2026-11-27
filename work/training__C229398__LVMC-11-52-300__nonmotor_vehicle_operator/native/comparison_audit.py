"""Independently compare the selected synthetic duration boundary probes."""

import argparse
import hashlib
import json
from pathlib import Path

from duration_policy import TARGETS, TOTAL_FRAMES, comparison_invariants


HERE = Path(__file__).resolve().parent.parent
AID = HERE.name


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(negative=False):
    configs = {}
    measured = {}
    construction_hashes = {}
    for suffix, target in TARGETS.items():
        construction_path = HERE / ("construction.json" if suffix == "below_30" else
                                    "cases/" + suffix + "/construction.json")
        construction = json.loads(construction_path.read_text())
        configs[suffix] = json.loads(next(item["content"] for item in construction["files"]
                                           if item["path"] == "config.json"))
        construction_hashes[suffix] = digest(construction_path)
        result_path = HERE / "physical" / suffix / "complete_motion-result.json"
        result = json.loads(result_path.read_text())
        observed = result.get("realized_observables", {}).get("night_parking_duration_ms")
        if result.get("diagnostic_fixture") is not True or observed != target * 1000:
            raise ValueError("Full-length synthetic duration probe differs")
        measured[suffix] = observed
    if negative:
        configs["above_30"]["weather"] = {"tampered": True}
    invariants = comparison_invariants(configs)
    if not (measured["below_30"] < 1800000 == measured["at_30"]
            < measured["above_30"] and
            all(config["capture_frames"] == TOTAL_FRAMES for config in configs.values())):
        raise ValueError("Strict thirty-minute bracket absent")
    return {"format": "c229398-duration-comparison-audit-v1",
            "comparison_id": AID + "__duration_boundary", "passed": True,
            "case_ids": [AID + "__" + suffix for suffix in TARGETS],
            "construction_sha256": construction_hashes,
            "held_fields": invariants["held_fields"],
            "duration_ms": measured, "diagnostic_fixture": True,
            "original_native_executed": False,
            "physical_or_legal_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-selftest", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.negative_selftest), sort_keys=True))


if __name__ == "__main__":
    main()
