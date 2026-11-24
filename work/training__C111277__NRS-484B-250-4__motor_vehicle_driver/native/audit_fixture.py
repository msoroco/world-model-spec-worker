"""Independent contrast and corruption audit for synthetic source measurements."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.source_root)
    a = measure(root / "halt")
    b = measure(root / "roll")
    require(a["frames"] == b["frames"] == 600, "duration changed")
    require(a["crosswalk_entry_frame"] == b["crosswalk_entry_frame"] == 300,
            "entry timing not held fixed")
    require(a["halt_before_crosswalk"] and not b["halt_before_crosswalk"],
            "halt contrast absent")
    require(a["yielded_until_other_clear"] and b["yielded_until_other_clear"],
            "yield policy changed")
    require(a["other_first_stop_frame"] == b["other_first_stop_frame"] and
            a["other_last_inside_frame"] == b["other_last_inside_frame"],
            "conflict history changed")
    require(sha(root / "halt" / "geometry.json") == sha(root / "roll" / "geometry.json"),
            "geometry changed")
    require(sha(root / "halt" / "signal.json") == sha(root / "roll" / "signal.json"),
            "signal changed")
    # A malicious edit to a retained row must be rejected by its source binding.
    row_path = root / "roll" / "native-rows.jsonl"
    old = row_path.read_bytes()
    try:
        row_path.write_bytes(old.replace(b'"ego_speed_mps": 2.333333',
                                         b'"ego_speed_mps": 0.000000', 1))
        rejected = False
        try:
            measure(root / "roll")
        except ValueError as exc:
            rejected = "source hash mismatch" in str(exc)
        require(rejected, "altered Native row not rejected")
    finally:
        row_path.write_bytes(old)
    result = {"format": "nrs-484b-250-4-independent-diagnostic-audit-v1",
              "passed": True, "halt_source_index_sha256": a["source_index_sha256"],
              "roll_source_index_sha256": b["source_index_sha256"],
              "same_entry_frame": 300, "same_signal_geometry_and_conflict_history": True,
              "halt_contrast": [True, False], "source_corruption_rejected": True,
              "physical_acceptance_claimed": False}
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "halt_contrast": [True, False],
                      "corruption_rejected": True}))


if __name__ == "__main__":
    main()
