"""Check documentary source joins for the conditional taxistand branch.

This verifies provenance fields and quoted source bytes. It does not establish
document authenticity or the legal applicability of a municipal designation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from candidate_opendrive import inspect as inspect_xodr
from stand_route import inspect as inspect_route

ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"
REQUIRED = ("cab_license", "stand_designation", "stand_marking",
            "posted_notice", "jurisdiction", "designation_provisions")


def _source(source: dict, root: Path, kind: str) -> dict:
    if not isinstance(source, dict) or not all(source.get(key) for key in
            ("path", "sha256", "record_id", "review_note", "quote")):
        raise ValueError(kind + " lacks a reviewed source descriptor")
    relative = Path(source["path"])
    if relative.is_absolute() or not relative.parts or relative.parts[0] != "reviewed_sources":
        raise ValueError(kind + " source must be retained under reviewed_sources")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(kind + " original source absent")
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(kind + " original source hash differs")
    try:
        original_text = path.read_text()
    except UnicodeDecodeError as exc:
        raise ValueError(kind + " needs a retained UTF-8 source extraction") from exc
    if source["quote"] not in original_text:
        raise ValueError(kind + " quote absent from retained original source")
    return {"path": source["path"], "sha256": source["sha256"],
            "record_id": source["record_id"]}


def validate(packet: dict, source_root: Path, map_path: Path, layout_path: Path) -> dict:
    layout = json.loads(layout_path.read_text())
    inspect_route(layout)
    map_data = map_path.read_bytes()
    inspect_xodr(map_data, layout["case"])
    expected_case = ASSIGNMENT + "__" + layout["case"]
    if (packet.get("format") != "c150530-reviewed-context-v1" or
            packet.get("assignment_id") != ASSIGNMENT or
            packet.get("case_id") != expected_case or
            packet.get("law_id") != "LVMC-11-60-090" or
            packet.get("actor") != "taxi_driver"):
        raise ValueError("reviewed context identity differs")
    if packet.get("map_sha256") != hashlib.sha256(map_data).hexdigest():
        raise ValueError("reviewed context map hash differs")
    if packet.get("stand_center_m") != layout["stand"]["center"] or packet.get("notice_point_m") != layout["posted_notice"]["point"]:
        raise ValueError("reviewed context feature positions differ")
    if packet.get("notice_meaning") != "right turn at first street intersection":
        raise ValueError("reviewed notice meaning differs")
    entries = packet.get("sources")
    if not isinstance(entries, dict) or set(entries) != set(REQUIRED):
        raise ValueError("reviewed context source coverage incomplete")
    verified = {key: _source(entries[key], source_root, key) for key in REQUIRED}
    return {"format": "c150530-reviewed-context-join-v1",
            "case_id": expected_case, "map_sha256": packet["map_sha256"],
            "sources": verified,
            "limitation": "Byte and quote join only; authenticity, designation authority and legal applicability require independent review"}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("packet", "source_root", "map", "layout", "output"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text())
    result = validate(packet, args.source_root, args.map, args.layout)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
