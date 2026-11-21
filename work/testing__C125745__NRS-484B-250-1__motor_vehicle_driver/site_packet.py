"""Bind the subsection (1) construction to the same C125745 median-site sources.

The source site is synthetic.  This is a CPU construction input and provenance
check, not evidence that the sign is official or that Native motion occurred.
"""

import hashlib
import json
from pathlib import Path

from stop_sign_control import validate_site


SIBLING = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver"
SITE_SHA256 = "a72765662459a1dd85101835279c82c74c6c711fcf212ba8035085c813765872"
CLAIMS = {
    "crossing_geometry_source": ("native_map_name", "intersection_id",
                                 "crossing_polygon_xy_m", "same_statutory_crossing"),
    "all_entrances_source": ("intersection_id", "all_entrance_road_lanes"),
    "sign_governance_source": ("stop_sign", "all_entrance_road_lanes"),
    "sign_face_video_source": ("stop_sign",),
    "median_spacing_source": ("intersection_id", "same_statutory_crossing"),
}


def _read_bound(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("C125745 site source SHA mismatch: " + str(path))
    return json.loads(data)


def load_site(root=None):
    """Return subsection (1) poses, governance sources and four camera poses.

    The two statutory subsections use the same selected C125745 junction and
    sign, so only physical site fields are reused.  Legal predicates are not.
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    sibling = (root / SIBLING).resolve()
    if not sibling.is_relative_to(root.resolve()):
        raise ValueError("Site source escaped work root")
    source = _read_bound(sibling / "site.json", SITE_SHA256)
    if (source.get("format") != "worker-stop-median-site-review" or
            source.get("review_status") != "reviewed_candidate" or
            source.get("approach_relation") != "different_highways" or
            source.get("same_statutory_crossing") is not True or
            set(source.get("camera_poses", {})) !=
            {"overview", "approach", "reference_corner", "driver_reference"}):
        raise ValueError("Expected C125745 median stop-sign scene missing")
    refs = source.get("source_refs")
    docs = source.get("source_documents")
    if not isinstance(refs, dict) or not isinstance(docs, dict) or set(refs) != set(CLAIMS) or set(docs) != set(CLAIMS):
        raise ValueError("Complete sourced site inventory required")
    for role, keys in CLAIMS.items():
        ref = docs[role]
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError("Hashed site review source required: " + role)
        relative = Path(ref["path"])
        path = (sibling / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(sibling):
            raise ValueError("Site review source escaped assignment")
        if refs[role] != relative.as_posix():
            raise ValueError("Site review source path differs: " + role)
        document = _read_bound(path, ref["sha256"])
        if (document.get("format") != "worker-stop-median-site-source" or
                document.get("source_role") != role or
                not document.get("review_basis") or
                not isinstance(document.get("reviewed_site_fields"), dict)):
            raise ValueError("Structured site review source required: " + role)
        claims = document["reviewed_site_fields"]
        if not set(keys) <= set(claims) or any(source.get(k) != v for k, v in claims.items()):
            raise ValueError("Site claim differs from review source: " + role)
    ego, other = (source["approaches"][role] for role in ("ego", "other"))
    if (ego["highway_id"] == other["highway_id"] or
            ego["road_id"] == other["road_id"] or
            source["stop_sign"]["governed_lane_id"] != ego["lane_id"]):
        raise ValueError("Distinct approach highways and ego sign governance required")
    center = [15, 0, 0]
    site = {
        "native_map_name": source["native_map_name"],
        "junction_id": source["intersection_id"],
        "highway_ids": {"ego": ego["highway_id"], "other": other["highway_id"]},
        "ego_approach": ego["spawn_pose"],
        "ego_entry": center + [ego["spawn_pose"][3]],
        "other_approach": other["spawn_pose"],
        "other_entry": center + [other["spawn_pose"][3]],
        "crossing_polygon_xy_m": source["crossing_polygon_xy_m"],
        "crossing_source": refs["crossing_geometry_source"],
        "median_opening_source": refs["median_spacing_source"],
        "different_highways_source": refs["all_entrances_source"],
        "device_inventory_source": refs["all_entrances_source"],
        "sign_erection_source": refs["sign_governance_source"],
        "camera_plan_source": refs["sign_face_video_source"],
        "camera_poses": source["camera_poses"],
        "stop_sign_native_id": source["stop_sign"]["native_id"],
        "site_source": str((sibling / "site.json").relative_to(root)),
        "site_source_sha256": SITE_SHA256,
        "review_status": "synthetic_cpu_candidate",
    }
    validate_site(site)
    return site
