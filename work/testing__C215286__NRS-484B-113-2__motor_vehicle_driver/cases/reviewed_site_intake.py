"""Check a proposed six-case Native site bundle before binding it to constructions.

This is a structural and byte-integrity check. A named review declaration is
not independent verification of the district, marking, map, or camera view.
"""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = ("site_packet.json", "intersection_site.json", "intersection_stop_site.json",
         "street_corner_site.json", "street_corner_stop_site.json")
SOURCE_KEYS = {
    NAMES[0]: ("district_source", "crosswalk_geometry_source", "crosswalk_marking_source"),
    NAMES[1]: ("geometry_source", "camera_source"),
    NAMES[2]: ("geometry_source", "camera_source"),
    NAMES[3]: ("geometry_source", "camera_source", "road_topology_source"),
    NAMES[4]: ("geometry_source", "camera_source", "road_topology_source"),
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root, row, key):
    if not isinstance(row, dict) or not isinstance(row.get("path"), str):
        raise ValueError("Missing source binding: " + key)
    rel = Path(row["path"])
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or row["path"] in (".", ""):
        raise ValueError("Unsafe source path: " + key)
    path = root / rel
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Missing or escaping source: " + key)
    if path.stat().st_size == 0 or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Empty or oversized source: " + key)
    path.read_text(encoding="utf-8")
    actual = _sha(path)
    if row.get("sha256") != actual:
        raise ValueError("Changed source: " + key)
    return {"path": str(rel), "sha256": actual}


def _review(packet, name):
    if packet.get("site_review_status") != "reviewed_native_site":
        raise ValueError("Original Native site review required: " + name)
    fields = (("reviewer", "district_review_basis", "crosswalk_review_basis",
               "camera_review_basis") if name == NAMES[0] else
              ("site_reviewer", "site_review_basis", "camera_review_basis"))
    for key in fields:
        value = packet.get(key)
        if not isinstance(value, str) or not value.strip() or "synthetic" in value.lower() or "diagnostic" in value.lower():
            raise ValueError("Original review declaration required: " + name + ":" + key)
    if packet.get("native_map_id") in (None, "", "TownX"):
        raise ValueError("Original Native map identity required: " + name)
    if type(packet.get("road_id")) is not int:
        raise ValueError("Original road identity required: " + name)


def check(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Reviewed source directory missing")
    packets = {}
    sources = {}
    for name in NAMES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Reviewed site packet missing: " + name)
        packet = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("Site packet must be an object: " + name)
        _review(packet, name)
        sources[name] = {key: _source(root, packet.get(key), key) for key in SOURCE_KEYS[name]}
        packets[name] = packet
    crosswalk = packets[NAMES[0]]
    if crosswalk.get("district_kind") != "residence" or type(crosswalk.get("crosswalk_id")) is not int:
        raise ValueError("Residence district or crosswalk identity missing")
    for name in NAMES[1:]:
        packet = packets[name]
        if (packet["native_map_id"], packet["road_id"]) != (crosswalk["native_map_id"], crosswalk["road_id"]):
            raise ValueError("Selected pair map or road identity differs: " + name)
        alternative = "intersection" if name.startswith("intersection") else "street_corner"
        expected_entry = not name.endswith("_stop_site.json")
        if packet.get("alternative") != alternative or packet.get("expected_entry") is not expected_entry:
            raise ValueError("Selected alternative identity differs: " + name)
    for entry, stop in ((NAMES[1], NAMES[2]), (NAMES[3], NAMES[4])):
        for key in ("region_polygon_xy_m", "geometry_source", "camera_source"):
            if packets[entry].get(key) != packets[stop].get(key):
                raise ValueError("Paired region/source differs: " + key)
    return {"format": "worker-c215286-reviewed-site-intake", "status": "structural_only",
            "native_map_id": crosswalk["native_map_id"], "road_id": crosswalk["road_id"],
            "site_packets": {name: {"sha256": _sha(root / name), "sources": sources[name]} for name in NAMES},
            "actual_native_geometry_verified": False, "actual_camera_pixels_reviewed": False,
            "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.source_directory), indent=2, sort_keys=True))
