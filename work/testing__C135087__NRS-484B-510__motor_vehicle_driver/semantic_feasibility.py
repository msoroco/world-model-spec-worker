"""Derive physical timing coverage from sealed original runs, without legal cutoffs."""

import hashlib
import json
from pathlib import Path

from zone_audit import audit_original_frames


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_original(attempt, case_id):
    attempt = Path(attempt)
    original = attempt / "original-attempt"
    seal = original / "seal.json"
    if not seal.is_file():
        raise ValueError("sealed original Native attempt missing")
    record = json.loads(seal.read_text())
    if record.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic attempt cannot establish feasible timing")
    site = original / "site-packet.json"
    if not site.is_file() or record.get("site_packet_sha256") != _sha(site):
        raise ValueError("original site packet missing or stale")
    history = original / "history.jsonl"
    audit_original_frames(history, original / "context.json", seal, case_id)
    packet = json.loads(site.read_text())
    if packet.get("case_id") != case_id or not packet.get("native_binding"):
        raise ValueError("original Native site binding missing or case mismatch")
    identity = {"map_id": packet.get("map_id"),
                "restricted_purpose": packet.get("restricted_purpose"),
                "zone_start_m": packet.get("zone_start_m"),
                "zone_end_m": packet.get("zone_end_m"),
                "sources": {role: item.get("sha256") for role, item in
                            packet.get("sources", {}).items()},
                "native_binding": packet["native_binding"]}
    identity_sha = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    return identity_sha, rows


def _first(rows, predicate):
    return next((row["time_s"] for row in rows if predicate(row)), None)


def describe_run(rows):
    """Classify observed relative timing; labels are physical, not legal verdicts."""
    exchange_start = _first(rows, lambda row: row["passenger_exchange_active"])
    exchange_end = max((row["time_s"] for row in rows if row["passenger_exchange_active"]),
                       default=None)
    entrant_motion = _first(rows, lambda row: row["entrant_parking_task_active"] and
                            row["entrant_speed_mps"] > .1)
    entrant_wait = _first(rows, lambda row: row["entrant_waiting"])
    access_blocked = _first(rows, lambda row: row["entrant_access_blocked"])
    if exchange_start is None or exchange_end is None or entrant_motion is None:
        raise ValueError("observed exchange or entrant motion absent")
    if entrant_motion < exchange_start:
        relation = "before_exchange"
    elif entrant_motion <= exchange_end:
        relation = "during_exchange"
    else:
        relation = "after_exchange"
    stationary = [row["time_s"] for row in rows if row["subject_speed_mps"] < .1]
    if not stationary:
        raise ValueError("observed subject stop absent")
    return {"relation": relation, "entrant_motion_s": entrant_motion,
            "exchange_start_s": exchange_start, "exchange_end_s": exchange_end,
            "entrant_wait_s": entrant_wait, "access_blocked_s": access_blocked,
            "subject_stationary_span_s": stationary[-1] - stationary[0],
            "legal_temporary": "unresolved_judgment",
            "legal_interference": "unresolved_judgment",
            "legal_about_to_enter": "unresolved_judgment"}


def derive(attempts):
    """Require three distinct source-sealed cases and a common reviewed site."""
    if not isinstance(attempts, dict) or len(attempts) != 3:
        raise ValueError("three original timing cases required")
    sites, runs = set(), {}
    for case_id, attempt in attempts.items():
        site_sha, rows = _load_original(attempt, case_id)
        sites.add(site_sha)
        runs[case_id] = describe_run(rows)
    if len(sites) != 1:
        raise ValueError("original timing cases use different reviewed sites")
    if {run["relation"] for run in runs.values()} != {
            "before_exchange", "during_exchange", "after_exchange"}:
        raise ValueError("original timing cases do not span three physical relations")
    motion = [run["entrant_motion_s"] for run in runs.values()]
    dwell = [run["subject_stationary_span_s"] for run in runs.values()]
    return {"reviewed_site_identity_sha256": next(iter(sites)), "runs": runs,
            "observed_entrant_motion_range_s": [min(motion), max(motion)],
            "observed_subject_stationary_span_range_s": [min(dwell), max(dwell)],
            "coverage_kind": "physical_timing_only",
            "legal_cutoffs": "unresolved_judgment"}
