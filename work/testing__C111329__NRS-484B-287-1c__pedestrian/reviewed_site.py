"""Require a reviewed original source packet before Native site construction.

The packet records physical/site provenance. Source presence does not decide
legal adjacency, official status, or the NRS 484B.290 exception.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from delivery_audit import CASES
from site_geometry import assess_site

REQUIRED_REVIEWS = ("topology", "highway", "device_authority",
                    "device_operation", "device_inventory", "camera_placement",
                    "marking_survey", "exception_290")


def _read_ref(ref: dict, *, base: Path) -> Path:
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("review source reference missing")
    path = Path(ref["path"])
    if not path.is_absolute():
        path = base / path
    if not path.is_file() or path.is_symlink() or \
       hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("review source missing or hash mismatch: " + str(ref["path"]))
    return path


def load_reviewed_site(path: str | Path, *, expected_case_id: str) -> dict:
    if expected_case_id not in CASES:
        raise ValueError("unknown exact NRS 484B.287(1)(c) case")
    path = Path(path).resolve()
    review = json.loads(path.read_text())
    if review.get("format") != "reviewed-c111329-between-intersections-site" or \
       review.get("cell_id") != "C111329" or \
       review.get("case_id") != expected_case_id or \
       not review.get("reviewer") or not review.get("method"):
        raise ValueError("exact fixed-cell site review missing")
    refs = review.get("sources")
    if not isinstance(refs, dict) or not all(name in refs for name in
            ("packet", "opendrive", *REQUIRED_REVIEWS)):
        raise ValueError("original reviewed site source inventory incomplete")
    sources = {key: _read_ref(refs[key], base=path.parent) for key in
               ("packet", "opendrive", *REQUIRED_REVIEWS)}
    xml = ElementTree.parse(sources["opendrive"]).getroot()
    if xml.tag != "OpenDRIVE" or len(xml.findall("./junction")) < 2:
        raise ValueError("original OpenDRIVE has no two-junction site")
    packet = json.loads(sources["packet"].read_text())
    if packet.get("cell_id") != "C111329" or packet.get("case_id") != expected_case_id:
        raise ValueError("source packet exact case or cell differs")
    site = assess_site(packet, require_operating=False)
    road_junction_ids = {node.attrib.get("id") for node in xml.findall("./junction")}
    if not set(site["between_junction_ids"]) <= road_junction_ids:
        raise ValueError("reviewed junction IDs absent from original OpenDRIVE")
    marked, operating = CASES[expected_case_id]
    if site["marked_crosswalk_present"] is not marked or \
       site["device_operation_observed"] is not operating:
        raise ValueError("reviewed packet differs from exact case distinction")
    return {"packet": packet, "site": site,
            "review_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_sha256": {name: refs[name]["sha256"] for name in sources},
            "legal_adjacency": "undetermined",
            "legal_official_status": "undetermined",
            "nrs_484b_290_exception": "undetermined"}
