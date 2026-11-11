"""Bind a reviewed median-site plan to retained source documents by hash."""
import hashlib
import json
from pathlib import Path
from median_spacing import check_roadway_pair

SOURCE_KEYS = ("polygon_source", "entrance_source", "median_spacing_source",
               "device_review_source", "statutory_crossing_review_source",
               "approach_geometry_source")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_device_review(document: dict, site: dict) -> dict:
    """Require a reviewed entrance inventory; Native actor checks remain separate."""
    if not isinstance(document, dict) or document.get("format") != "worker-median-device-inventory":
        raise ValueError("Structured official-device inventory required")
    if document.get("crossing_id") != site.get("crossing_id") or document.get("native_map_name") != site.get("native_map_name"):
        raise ValueError("Official-device inventory differs from selected crossing")
    if document.get("all_entrances_reviewed") is not True or not isinstance(document.get("review_basis"), str) or not document["review_basis"].strip():
        raise ValueError("Complete sourced entrance/device review required")
    entrances = document.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2:
        raise ValueError("At least two reviewed crossing entrances required")
    identities = set()
    highways = set()
    for entrance in entrances:
        if not isinstance(entrance, dict) or any(type(entrance.get(key)) is not int
                for key in ("road_id", "lane_id", "highway_id")):
            raise ValueError("Sourced road, lane and highway identity required at every entrance")
        identity = (entrance["road_id"], entrance["lane_id"])
        if identity in identities:
            raise ValueError("Duplicate reviewed crossing entrance")
        identities.add(identity)
        highways.add(entrance["highway_id"])
    if {site.get("ego_highway_id"), site.get("other_highway_id")} - highways:
        raise ValueError("Selected highways missing from reviewed entrances")
    devices = document.get("devices")
    if not isinstance(devices, list):
        raise ValueError("Explicit official-device list required, including empty list")
    for device in devices:
        if not isinstance(device, dict) or not device.get("type") or not device.get("source") or type(device.get("controls_crossing")) is not bool:
            raise ValueError("Sourced device identity and control status required")
        if device["controls_crossing"]:
            raise ValueError("Official device controls selected crossing")
    return {"reviewed_entrance_count": len(entrances), "reviewed_device_count": len(devices),
            "entrance_road_lanes": [list(pair) for pair in sorted(identities)],
            "official_device_controls_crossing": False,
            "review_basis": document["review_basis"]}


def verify_site_packet(config, base_dir: Path) -> dict:
    reference = config.get("site_review")
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("Hashed site review packet required")
    path = Path(reference["path"])
    if not path.is_absolute():
        path = Path(base_dir) / path
    if not path.is_file() or _sha(path) != reference["sha256"]:
        raise ValueError("Site review packet missing or changed")
    packet = json.loads(path.read_text())
    if packet.get("format") != "worker-median-site-review" or packet.get("review_status") != "reviewed_candidate":
        raise ValueError("Reviewed median site packet required")
    if packet.get("site") != config.get("site"):
        raise ValueError("Site config differs from reviewed packet")
    docs = packet.get("source_documents")
    if not isinstance(docs, dict) or set(docs) != set(SOURCE_KEYS):
        raise ValueError("Complete site source document inventory required")
    verified = {}
    for key in SOURCE_KEYS:
        source = docs[key]
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            raise ValueError("Hashed site source required: " + key)
        if config["site"].get(key) != source["path"]:
            raise ValueError("Site source reference differs: " + key)
        source_path = Path(source["path"])
        if not source_path.is_absolute():
            source_path = path.parent / source_path
        if not source_path.is_file() or _sha(source_path) != source["sha256"]:
            raise ValueError("Site source missing or changed: " + key)
        verified[key] = {"path": str(source_path), "sha256": source["sha256"]}
    spacing_path = Path(verified["median_spacing_source"]["path"])
    spacing = check_roadway_pair(json.loads(spacing_path.read_text()),
                                 config["site"].get("crossing_polygon_xy_m"),
                                 config["site"].get("selected_roadway_index"))
    device_path = Path(verified["device_review_source"]["path"])
    device_review = verify_device_review(json.loads(device_path.read_text()),
                                         config["site"])
    return {"packet_path": str(path), "packet_sha256": reference["sha256"],
            "source_documents": verified,
            "median_spacing_measurement": spacing,
            "device_review": device_review,
            "physical_site_verified": False, "statutory_identity_verified": False}
