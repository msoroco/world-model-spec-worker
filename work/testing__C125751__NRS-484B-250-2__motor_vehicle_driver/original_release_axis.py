"""Audit a four-point release axis from sealed original Native attempts.

This is an engineering feasibility comparison, never a legal time threshold.
"""

import hashlib
import importlib.util
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "c125751_diagnostic_builder", HERE / "build_diagnostic_constructions.py")
_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_builder)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check_controls(path, role, release):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(rows) < 1100:
        raise ValueError("Full original controller history required")
    held_before, driven_after = False, False
    for index, row in enumerate(rows):
        permission = row.get("release_permissions", {}).get(role)
        control = row.get(role + "_control")
        if type(permission) is not bool or not isinstance(control, dict):
            raise ValueError("Original permission and applied control required")
        if permission != (index >= release):
            raise ValueError("Original permission differs from release schedule")
        hold, brake, throttle = (control.get(key) for key in ("hold", "brake", "throttle"))
        if type(hold) is not bool or any(type(value) not in (int, float) or
                                          not math.isfinite(value) or value < 0 or value > 1
                                          for value in (brake, throttle)):
            raise ValueError("Finite original brake/throttle control required")
        if index < release and hold and brake >= .99 and throttle == 0:
            held_before = True
        if index >= release and permission and not hold and throttle > 0:
            driven_after = True
    if not held_before or not driven_after:
        raise ValueError("Original stop-and-release control transition unproved")
    return {"held_before_release": held_before, "driven_after_release": driven_after,
            "controller_frames": len(rows)}


def audit_axis(attempts, role):
    """Require four fixed-condition captures with a measured entry response."""
    if role not in ("ego", "other") or len(attempts) != 4:
        raise ValueError("Four attempts and one varied release role required")
    rows, fixed = [], None
    for attempt in map(Path, attempts):
        seal_path = attempt / "capture-seal.json"
        if not seal_path.is_file():
            raise ValueError("Original Native capture seal required: " + str(attempt))
        seal = json.loads(seal_path.read_text())
        if (seal.get("format") != "worker-sealed-capture"
                or seal.get("provenance_kind") != "native"
                or seal.get("diagnostic_fixture") is not False
                or seal.get("restoration", {}).get("restored") is not True
                or seal.get("frames", 0) < 1100):
            raise ValueError("Incomplete or diagnostic Native capture: " + str(attempt))
        sources = seal.get("sources", {})
        for name in ("config.json", "controller_history.jsonl", "crossing_history.jsonl",
                     "video_frames.jsonl", "trace.jsonl"):
            if not (attempt / name).is_file() or sources.get(name) != _sha(attempt / name):
                raise ValueError("Original source absent from sealed acquisition: " + name)
        config = json.loads((attempt / "config.json").read_text())
        release = config.get(role + "_release_frame")
        if type(release) is not int:
            raise ValueError("Varied release index required in every attempt")
        baseline = {key: value for key, value in config.items()
                    if key != role + "_release_frame"}
        if fixed is None:
            fixed = baseline
        elif baseline != fixed:
            raise ValueError("Fixed construction condition changed across release axis")
        controls = _check_controls(attempt / "controller_history.jsonl", role, release)
        measured = _builder.audit_release_attempt(attempt)
        entry = measured["first_body_entry"][role]["time_s"]
        delay = measured["release_to_entry_delay_s"][role]
        if not all(math.isfinite(float(v)) for v in (entry, delay)):
            raise ValueError("Finite original release and entry measurements required")
        rows.append({"attempt": str(attempt), "capture_seal_sha256": _sha(seal_path),
                     "release_frame": release, "entry_time_s": entry,
                     "release_to_entry_delay_s": delay,
                     "control_transition": controls,
                     "source_hashes": measured["sources"]})
    rows.sort(key=lambda row: row["release_frame"])
    if len({row["release_frame"] for row in rows}) != 4:
        raise ValueError("Four distinct release points required")
    entries = [row["entry_time_s"] for row in rows]
    if any(right < left for left, right in zip(entries, entries[1:])):
        raise ValueError("Original body entry reverses release ordering")
    if entries[-1] <= entries[0]:
        raise ValueError("Original body entry did not respond to release variation")
    return {"format": "worker-original-release-axis", "varied_role": role,
            "rows": rows, "measured_entry_range_s": [entries[0], entries[-1]],
            "fixed_config_sha256": hashlib.sha256(json.dumps(
                fixed, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "physical_acceptance_claimed": False, "legal_threshold_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("ego", "other"))
    parser.add_argument("attempts", nargs=4)
    args = parser.parse_args()
    print(json.dumps(audit_axis(args.attempts, args.role), indent=2))
