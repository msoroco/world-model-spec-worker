"""Independent diagnostic bridge and viaduct lateral contrasts."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(kind, swap=False):
    if kind not in ("bridge", "viaduct"):
        raise ValueError("Unknown structure comparison")
    proofs = {}
    for side in ("right", "left"):
        suffix = kind + "_" + side
        folder = HERE / "structure-fixture-source" / suffix
        receipt = HERE / "selected-proofs" / (suffix + "-primary-compatibility.json")
        data = json.loads(receipt.read_text())
        value = data["measurement_examples"]["structure_approach"]["value"]
        proofs[side] = {"receipt_sha256": sha(receipt), "value": value,
            "context_sha256": {source: sha(folder / source) for source in
                ("structure-geometry.json", "road-direction-survey.json",
                 "centreline-geometry.json")},
            "rows": [json.loads(line) for line in
                (folder / "structure-rows.jsonl").read_text().splitlines()]}
    right, left = proofs["right"], proofs["left"]
    if swap:
        left["value"] = right["value"]
    if right["context_sha256"] != left["context_sha256"]:
        raise ValueError("Fixed structure context differs")
    if any(len(item["rows"]) != 600 for item in (right, left)):
        raise ValueError("Incomplete 600-frame comparison")
    right_value, left_value = right["value"], left["value"]
    if (right_value["within_100_ft_driving_frames"] !=
            left_value["within_100_ft_driving_frames"] or
            right_value["blocked_sight_within_zone_frames"] !=
            left_value["blocked_sight_within_zone_frames"] or
            right_value["left_and_blocked_within_zone_frames"] != 0 or
            left_value["left_and_blocked_within_zone_frames"] <= 0):
        raise ValueError("Controlled lateral contrast absent")
    return {"comparison_id": HERE.name + "__" + kind + "_comparison",
        "case_ids": [HERE.name + "__" + kind + "_" + side for side in ("right", "left")],
        "context_sha256": right["context_sha256"],
        "left_and_blocked_frames": [right_value["left_and_blocked_within_zone_frames"],
                                    left_value["left_and_blocked_within_zone_frames"]],
        "cpu_diagnostic_only": True, "original_native_observed": False,
        "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True)
    parser.add_argument("--negative-swap", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.kind, args.negative_swap), sort_keys=True))
