"""Independent fixed-context one-way tunnel comparison from saved CPU receipts."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
NAMES = ("one_way_right", "one_way_left")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(swap=False):
    proofs = {}
    for name in NAMES:
        folder = HERE / "fixture-source" / name
        receipt = HERE / "selected-proofs" / (name + "-primary-compatibility.json")
        data = json.loads(receipt.read_text())
        value = data["measurement_examples"]["tunnel_approach"]["value"]
        proofs[name] = {"receipt_sha256": digest(receipt), "value": value,
            "context_sha256": {source: digest(folder / source) for source in
                ("portal-geometry.json", "road-direction-survey.json", "centreline-geometry.json")},
            "rows": [json.loads(line) for line in (folder / "tunnel-rows.jsonl").read_text().splitlines()]}
    first, second = (proofs[name] for name in NAMES)
    if swap:
        second["value"] = first["value"]
    if first["context_sha256"] != second["context_sha256"]:
        raise ValueError("Fixed one-way tunnel context differs")
    if any(len(item["rows"]) != 600 for item in (first, second)):
        raise ValueError("Incomplete 600-frame one-way comparison")
    values = [item["value"] for item in (first, second)]
    if (any(value["one_way_highway_surveyed"] is not True for value in values) or
            [(value["within_100_ft_driving_frames"],
              value["blocked_sight_within_zone_frames"],
              value["left_and_blocked_within_zone_frames"]) for value in values]
            != [(153, 153, 0), (153, 153, 153)]):
        raise ValueError("Controlled one-way lateral contrast absent")
    return {"comparison_id": HERE.name + "__one_way_comparison",
            "case_ids": [HERE.name + "__" + name for name in NAMES],
            "context_sha256": first["context_sha256"],
            "left_and_blocked_frames": [0, 153],
            "cpu_diagnostic_only": True, "original_native_observed": False,
            "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-swap", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.negative_swap), sort_keys=True))
