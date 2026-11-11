"""Bind the two-signal median-site candidate to exact retained source files.

Hashes establish which planning documents were checked. They do not prove a
physical signal head, official-device status, or statutory crossing identity.
"""
import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_bindings(site):
    references = site.get("selected_stop_references", {})
    heads = site.get("head_geometry_sources", {})
    if set(references) != {"ego", "other"} or set(heads) != {"ego", "other"}:
        raise ValueError("Two stop references and two head geometry sources required")
    if any(not isinstance(references[role], dict) for role in ("ego", "other")):
        raise ValueError("Two structured stop references required")
    return {
        "polygon": site.get("polygon_source"),
        "approaches": site.get("approach_geometry_source"),
        "device_inventory": site.get("device_inventory_source"),
        "cameras": site.get("camera_plan_source"),
        "ego_stop_geometry": references["ego"].get("geometry_source"),
        "ego_stop_review": references["ego"].get("reference_review_source"),
        "other_stop_geometry": references["other"].get("geometry_source"),
        "other_stop_review": references["other"].get("reference_review_source"),
        "ego_head_geometry": heads["ego"],
        "other_head_geometry": heads["other"],
    }


def _finite_point(value, length):
    return isinstance(value, list) and len(value) == length and all(
        type(x) in (int, float) and math.isfinite(x) for x in value)


def _check_content(kind, document, site):
    content = document.get("content")
    if not isinstance(content, dict):
        raise ValueError("Structured site source content required: " + kind)
    refs = site["selected_stop_references"]
    if kind == "polygon":
        valid = content.get("polygon_xy_m") == site["crossing_polygon_xy_m"]
    elif kind == "approaches":
        valid = content.get("approach_poses") == {role: site[role + "_approach"] for role in ("ego", "other")}
    elif kind == "device_inventory":
        valid = (content.get("governed_road_lanes") == site.get("expected_approach_lanes")
                 and content.get("all_entrances_reviewed") is True)
    elif kind == "cameras":
        valid = content.get("camera_poses") == site["cameras"]
    elif kind.endswith("_stop_geometry"):
        role = kind.split("_")[0]
        valid = content.get("segment_xy_m") == refs[role]["segment_xy_m"]
    elif kind.endswith("_stop_review"):
        role = kind.split("_")[0]
        valid = (content.get("selected_kind") == refs[role]["kind"]
                 and content.get("segment_xy_m") == refs[role]["segment_xy_m"])
    elif kind.endswith("_head_geometry"):
        role = kind.split("_")[0]
        valid = (content.get("governed_road_lane") == site.get("expected_approach_lanes", {}).get(role)
                 and _finite_point(content.get("head_world_location_xyz_m"), 3)
                 and content.get("planned_camera") in site["cameras"])
    else:
        valid = False
    if not valid:
        raise ValueError("Site source content differs from selected geometry: " + kind)


def verify_site_packet(config, base_dir):
    reference = config.get("site_review")
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("Hashed two-signal site review packet required")
    path = Path(reference["path"])
    if not path.is_absolute():
        path = Path(base_dir) / path
    if not path.is_file() or _sha(path) != reference["sha256"]:
        raise ValueError("Two-signal site review packet missing or changed")
    packet = json.loads(path.read_text())
    if packet.get("format") != "worker-c125751-two-signal-site-review" or packet.get("review_status") != "candidate_reviewed":
        raise ValueError("Reviewed two-signal site packet required")
    site = config.get("site")
    if packet.get("site") != site:
        raise ValueError("Site config differs from reviewed packet")
    bindings = source_bindings(site)
    documents = packet.get("source_documents")
    if not isinstance(documents, dict) or set(documents) != set(bindings):
        raise ValueError("Complete two-signal source inventory required")
    verified, diagnostic_only = {}, False
    for kind, path_string in bindings.items():
        source = documents[kind]
        if not isinstance(path_string, str) or not path_string.strip():
            raise ValueError("Missing site source reference: " + kind)
        if not isinstance(source, dict) or set(source) != {"path", "sha256"} or source["path"] != path_string:
            raise ValueError("Hashed site source differs: " + kind)
        source_path = Path(path_string)
        if not source_path.is_absolute():
            source_path = path.parent / source_path
        if not source_path.is_file() or _sha(source_path) != source["sha256"]:
            raise ValueError("Site source missing or changed: " + kind)
        document = json.loads(source_path.read_text())
        if (not isinstance(document, dict) or document.get("format") != "worker-c125751-site-source"
                or document.get("source_kind") != kind
                or document.get("native_map_name") != site.get("native_map_name")
                or document.get("crossing_id") != site.get("crossing_id")
                or not isinstance(document.get("review_basis"), str)
                or not document["review_basis"].strip()
                or type(document.get("diagnostic_only")) is not bool):
            raise ValueError("Site source identity/review invalid: " + kind)
        _check_content(kind, document, site)
        diagnostic_only = diagnostic_only or document["diagnostic_only"]
        verified[kind] = {"path": str(source_path), "sha256": source["sha256"]}
    return {"packet_path": str(path), "packet_sha256": reference["sha256"],
            "source_documents": verified, "diagnostic_only": diagnostic_only,
            "physical_site_verified": False, "official_device_status_verified": False,
            "head_pixel_visibility_verified": False}
