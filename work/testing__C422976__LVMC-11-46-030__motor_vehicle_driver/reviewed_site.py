"""Verify a reviewed original school-lane packet before Native construction."""

import hashlib
import json
import math
from pathlib import Path

from school_lane_controls import ASSIGNMENT, selected_schedule


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("source path escapes reviewed authority root")
    return path


def plan(root: Path, site_ref: dict, case_id: str) -> dict:
    """Return source-sealed local paths and engineering controls; no legal verdict."""
    selected_schedule(case_id, 0.0)
    if not isinstance(site_ref, dict) or not site_ref.get("path") or not site_ref.get("sha256"):
        raise ValueError("reviewed site reference with SHA-256 required")
    site_path = within(root, site_ref["path"])
    if sha(site_path) != site_ref["sha256"]:
        raise ValueError("reviewed site bytes changed")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("source_kind") != "reviewed_original_site" or site.get("cell_id") != "C422976":
        raise ValueError("original reviewed C422976 site required")
    if site.get("school_lane_control") != "school_crosswalk":
        raise ValueError("school pedestrian lane source missing")
    for field in ("opendrive", "nearest_side_geometry", "municipal_jurisdiction",
                  "vehicle_reference_point", "human_actor", "device_actor", "child_actor"):
        ref = site.get(field)
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            raise ValueError("reviewed source reference missing: " + field)
        if sha(within(root, ref["path"])) != ref["sha256"]:
            raise ValueError("reviewed source bytes changed: " + field)
    geometry = json.loads(within(root, site["nearest_side_geometry"]["path"]).read_text())
    station = geometry.get("nearest_side_station_m")
    if not isinstance(station, (int, float)) or not math.isfinite(station):
        raise ValueError("reviewed school-lane nearest-side station required")
    if geometry.get("approach_lane_id") is None or not geometry.get("school_lane_polygon_xy"):
        raise ValueError("reviewed approach lane and school-lane polygon required")
    if geometry.get("station_axis") != "world_x_positive":
        raise ValueError("reviewed positive-world-x station axis required")
    return {
        "assignment_id": ASSIGNMENT, "case_id": case_id, "variant": case_id[len(ASSIGNMENT) + 2:],
        "source_kind": "reviewed_original_site", "authority_root": str(root.resolve()),
        "site_path": str(site_path),
        "site_sha256": site_ref["sha256"],
        "map_path": str(within(root, site["opendrive"]["path"])),
        "opendrive_sha256": site["opendrive"]["sha256"],
        "nearest_side_geometry_sha256": site["nearest_side_geometry"]["sha256"],
        "nearest_side_station_m": float(station),
        "school_lane_polygon_xy": geometry["school_lane_polygon_xy"],
        "ego_approach_lane_id": geometry["approach_lane_id"],
        "station_axis": geometry["station_axis"],
        "municipal_jurisdiction_source": site["municipal_jurisdiction"],
        "vehicle_reference_point_source": site["vehicle_reference_point"],
        "human_actor_source": site["human_actor"],
        "device_actor_source": site["device_actor"],
        "child_actor_source": site["child_actor"],
        "stop_reference_station_target_m": selected_schedule(case_id, station)["ego_stop_reference_station_target_m"],
        "legal_judgment": "unresolved",
    }
