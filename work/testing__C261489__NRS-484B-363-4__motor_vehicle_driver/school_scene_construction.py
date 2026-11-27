"""Resolve reviewed original site bytes before a Native school-zone pass."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from school_pass import SOURCES, construct as construct_pass, validate_scene
from school_timing import HASH_FIELDS


TIMING_SOURCE = {
    "calendar_source_sha256": "school_calendar",
    "operation_schedule_source_sha256": "operation_schedule",
    "class_schedule_source_sha256": "class_schedule",
    "local_clock_source_sha256": "local_clock",
    "beacon_configuration_source_sha256": "beacon_configuration",
    "beacon_state_source_sha256": "beacon_state",
    "sign_instruction_source_sha256": "sign_instruction",
    "zone_designation_source_sha256": "zone_designation",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_site(path: Path, case_id: str) -> dict:
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    records = site.get("source_records")
    if not isinstance(records, dict) or set(records) != set(SOURCES):
        raise ValueError("reviewed original school-zone source inventory incomplete")
    for name in SOURCES:
        row = records[name]
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ValueError("reviewed source path missing: " + name)
        source = (path.parent / row["path"]).resolve()
        if path.parent not in source.parents or not source.is_file():
            raise ValueError("reviewed source outside original site packet: " + name)
        digest = sha(source)
        if digest != row.get("sha256") or digest != site.get(name + "_source_sha256"):
            raise ValueError("original school-zone source hash differs: " + name)
    timing = site.get("timing_packet", {})
    for field in HASH_FIELDS:
        if timing.get(field) != records[TIMING_SOURCE[field]]["sha256"]:
            raise ValueError("independent school timing/device source differs: " + field)
    if site.get("map_sha256") != records["map_geometry"]["sha256"]:
        raise ValueError("physical map source hash differs")
    validate_scene(site, case_id)
    site["_source_sha256"] = sha(path)
    return site


def construct(adapter, site_path: Path, case_id: str) -> dict:
    site = validate_site(site_path, case_id)
    return construct_pass(adapter, site, case_id)
