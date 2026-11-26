"""Bind an exact school crossing-zone case to reviewed original source bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from school_uturn import CASES, SOURCES, construct as construct_school, validate_scene


ASSIGNMENT = "testing__C255863__NRS-484B-363-3__motor_vehicle_driver"
ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(case_id):
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact school-zone case ID required")
    name = case_id[len(ASSIGNMENT) + 2:]
    for case in CASES:
        if case.name == name:
            return case
    raise ValueError("unknown exact school-zone case")


def validate_site(path, case_id):
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    case = load_case(case_id)
    if site.get("case_id") != case_id or site.get("map_sha256") is None:
        raise ValueError("reviewed exact school-zone site/map missing")
    records = site.get("source_records")
    if not isinstance(records, dict) or set(records) != set(SOURCES):
        raise ValueError("reviewed school-zone source inventory incomplete")
    for name in SOURCES:
        record = records[name]
        source = (path.parent / record["path"]).resolve()
        if path.parent not in source.parents or not source.is_file():
            raise ValueError("reviewed source outside packet: " + name)
        digest = sha(source)
        if digest != record.get("sha256") or digest != site.get(name + "_source_sha256"):
            raise ValueError("reviewed source hash differs: " + name)
    timing = site.get("timing_packet", {})
    timing_sources = {
        "calendar_source_sha256": "school_calendar",
        "operation_schedule_source_sha256": "school_operation_time",
        "class_schedule_source_sha256": "class_hours",
        "local_clock_source_sha256": "local_clock",
        "beacon_configuration_source_sha256": "beacon_configuration",
        "beacon_state_source_sha256": "beacon_state",
        "sign_instruction_source_sha256": "sign_instruction",
    }
    for field, name in timing_sources.items():
        if timing.get(field) != records[name]["sha256"]:
            raise ValueError("school timing source hash differs: " + name)
    validate_scene(site, case)
    site["_source_sha256"] = sha(path)
    return site


def construct(adapter, site_path, case_id):
    site = validate_site(site_path, case_id)
    return construct_school(adapter, site, load_case(case_id))
