"""Bind a reviewed median-site plan to retained source documents by hash."""
import hashlib
import json
from pathlib import Path
from median_spacing import check_roadway_pair

SOURCE_KEYS = ("polygon_source", "entrance_source", "median_spacing_source",
               "device_review_source", "statutory_crossing_review_source")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    return {"packet_path": str(path), "packet_sha256": reference["sha256"],
            "source_documents": verified,
            "median_spacing_measurement": spacing,
            "physical_site_verified": False, "statutory_identity_verified": False}
