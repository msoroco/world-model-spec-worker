"""Audit the source and physical isolation of a proposed officer direction pair.

Synthetic inputs test the auditor. They do not establish an original direction,
its applicability, physical acceptance, or a legal outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from native.branch_context import validate as validate_branch_context


ASSIGNMENT = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver"
PREFIX = ASSIGNMENT + "__selected_police_source__"
FIXED_CONFIG = ("law_id", "cell_id", "actor", "activity_request", "rate_hz",
                "duration_s", "frames", "vehicle_blueprint_id", "cameras", "park_y_m")
FIXED_ROW = ("time_s", "road_xy_m", "obstruction_xy_m",
             "obstruction_kind", "ego_body_xy_m", "ego_speed_m_s",
             "passing_body_xy_m", "passing_speed_m_s", "controller_clearance_m")


def _load(path: Path):
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def _rows(path: Path):
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root: Path, source_kind: str = "synthetic_cpu") -> dict:
    root = Path(root)
    if source_kind not in {"synthetic_cpu", "original_native"}:
        raise ValueError("Unknown police source kind")
    configs, contexts, rows, source_hashes = [], [], [], []
    for suffix in ("police_absent", "police_present"):
        case = root / "cases" / suffix
        source = root / "selected-source" / suffix
        config = _load(case / "config.json")
        context = _load(source / "exception-context.json")
        samples = _rows(source / "native_samples.jsonl")
        if config.get("case_id") != PREFIX + suffix or context.get("case_id") != config["case_id"]:
            raise ValueError("Police comparison case identity differs")
        required_context_kind = "reviewed_branch_context" if source_kind == "original_native" else "synthetic_cpu"
        if context.get("source_kind") != required_context_kind or not samples or any(
                row.get("source_kind") != source_kind for row in samples):
            raise ValueError("Police comparison lacks the declared source kind")
        if source_kind == "original_native":
            requested = "police_direction" if suffix == "police_present" else None
            validate_branch_context(source, source / "exception-context.json",
                                    config["case_id"], "park", requested)
            if any(row.get("context_sha256") != _sha(source / "exception-context.json")
                   for row in samples):
                raise ValueError("Original frames do not bind reviewed authority context")
        if context.get("activity_request") != "park" or config.get("activity_request") != "park":
            raise ValueError("Police comparison activity differs")
        if context.get("legal_verdict_claimed") is not False or config.get("legal_verdict_claimed") is not False:
            raise ValueError("Police comparison asserts a legal outcome")
        if config.get("physical_acceptance_claimed") is not False:
            raise ValueError("Police comparison asserts physical acceptance")
        if set(context.get("exception_source", {})) != {
                "traffic_conflict_reviewed", "law_direction_reviewed",
                "police_direction_reviewed", "traffic_device_reviewed"} or not all(
                context["exception_source"].values()):
            raise ValueError("Police comparison lacks separately reviewed exception sources")
        if len(samples) != config.get("frames") or len(samples) != config["duration_s"] * config["rate_hz"]:
            raise ValueError("Police comparison timeline incomplete")
        if any(samples[index]["native_frame"] >= samples[index + 1]["native_frame"]
               for index in range(len(samples) - 1)):
            raise ValueError("Police comparison frame identities are not increasing")
        configs.append(config)
        contexts.append(context)
        rows.append(samples)
        source_hashes.append({"context": _sha(source / "exception-context.json"),
                              "native_samples": _sha(source / "native_samples.jsonl")})
    if any(configs[0].get(k) is None or configs[0].get(k) != configs[1].get(k) for k in FIXED_CONFIG):
        raise ValueError("Police comparison changed a fixed construction condition")
    if contexts[0].get("exception_request") is not None or contexts[1].get("exception_request") != "police_direction":
        raise ValueError("Police direction axis did not change exactly")
    for index, (left, right) in enumerate(zip(*rows)):
        if any(left.get(k) is None or left[k] != right.get(k) for k in FIXED_ROW):
            raise ValueError("Police comparison changed fixed source at frame " + str(index))
        for row, present in ((left, False), (right, True)):
            exceptions = row.get("exceptions", {})
            if exceptions != {"traffic_conflict": False, "law_direction": False,
                              "police_direction": present, "traffic_device": False}:
                raise ValueError("Police comparison source axis differs at frame " + str(index))
            if row.get("exception_source") != contexts[0]["exception_source"]:
                raise ValueError("Police comparison source review differs at frame " + str(index))
    if contexts[0]["exception_source"] != contexts[1]["exception_source"]:
        raise ValueError("Police comparison source review differs")
    return {"format": "c135702-police-source-comparison-draft-v1", "passed": True,
            "source_kind": source_kind, "case_ids": [c["case_id"] for c in configs],
            "source_sha256": source_hashes, "frames_compared": len(rows[0]),
            "fixed_config": list(FIXED_CONFIG), "fixed_source": list(FIXED_ROW),
            "declared_difference": "police_direction_source_request",
            "original_authority_proven": source_kind == "original_native",
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source-kind", choices=("synthetic_cpu", "original_native"),
                        default="synthetic_cpu")
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.source_kind), sort_keys=True))
