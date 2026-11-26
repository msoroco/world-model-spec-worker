"""Source-gated original cycle-lane acquisition and saved observation audit.

The reviewer supplies the three expected hashes independently. This module
never decides the subsection 3 exception or a legal violation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT
from cycle_lane_site import _breaks, _inside, _polygon, construct

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _intersects(a, b) -> bool:
    return (any(_inside(point, b) for point in a) or
            any(_inside(point, a) for point in b) or
            any(_breaks(a[i], a[(i + 1) % len(a)], b) for i in range(len(a))))


def _sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing or linked: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_sealed(root: Path, reference: dict) -> dict:
    if not isinstance(reference, dict) or not reference.get("path") or not reference.get("sha256"):
        raise ValueError("source reference and SHA-256 required")
    path = root / reference["path"]
    if not path.resolve().is_relative_to(root.resolve()) or _sha(path) != reference["sha256"]:
        raise ValueError("original source changed or escaped attempt")
    return json.loads(path.read_text(encoding="utf-8"))


def audit(attempt_root: str | Path, reviewed_site_sha256: str,
          reviewed_exception_sha256: str, reviewed_vehicle_sha256: str) -> dict:
    root = Path(attempt_root).resolve()
    if (root / "attempt-source.json").is_symlink():
        raise ValueError("linked attempt source seal rejected")
    seal = json.loads((root / "attempt-source.json").read_text(encoding="utf-8"))
    case_id = seal.get("case_id")
    if (seal.get("format") != "cycle-lane-native-attempt-v1" or
            seal.get("source_kind") != "original_native" or
            seal.get("diagnostic_fixture") is not False or
            not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__")):
        raise ValueError("original Native cycle-lane attempt required")
    for name, expected in (("site", reviewed_site_sha256),
                           ("subsection_3", reviewed_exception_sha256),
                           ("vehicle", reviewed_vehicle_sha256)):
        if not isinstance(expected, str) or len(expected) != 64 or seal.get(name, {}).get("sha256") != expected:
            raise ValueError("independent reviewed " + name + " hash required")
    site = _read_sealed(root, seal["site"])
    exception = _read_sealed(root, seal["subsection_3"])
    vehicle = _read_sealed(root, seal["vehicle"])
    if (site.get("assignment_id") != ASSIGNMENT or not site.get("designation_authority") or
            site.get("source_kind") != "original_reviewed" or
            not site.get("intersection_is_public_highway_junction") or
            not site.get("not_alley_junction") or
            not site.get("cycle_lane_designated_for")):
        raise ValueError("reviewed public intersection and lane designation required")
    if (exception.get("source_kind") != "original_reviewed" or
            exception.get("law_id") != "NRS-484B-270-3" or
            exception.get("status") not in ("applies", "does_not_apply", "unresolved") or
            not exception.get("authoritative_clause") or not exception.get("reviewer")):
        raise ValueError("reviewed subsection 3 clause and status required")
    spawned_actor_id = seal.get("spawned_actor_id")
    if (vehicle.get("source_kind") != "original_reviewed" or
            vehicle.get("vehicle_type") != "motor_vehicle" or
            not vehicle.get("blueprint_id") or
            not vehicle.get("driver_identity_source") or
            seal.get("vehicle_blueprint_id") != vehicle["blueprint_id"] or
            not isinstance(spawned_actor_id, int) or isinstance(spawned_actor_id, bool) or
            spawned_actor_id <= 0):
        raise ValueError("reviewed motor vehicle and driver required")
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    case = next((item for item in plan["cases"] if item["case_id"] == case_id), None)
    if case is None or exception["status"] != case["requested_subsection_3_exception_status"]:
        raise ValueError("case subsection 3 status differs from source")
    route = construct(root / seal["site"]["path"], seal.get("route_candidate_id", ""),
                      case["requested_cycle_lane_intersection_overlap"])
    intersection_polygon = _polygon(site.get("intersection_polygon"))
    cycle_lane_polygon = _polygon(site.get("cycle_lane_polygon"))
    rows = _read_sealed(root, seal.get("history"))
    if not isinstance(rows, list) or len(rows) != 900:
        raise ValueError("900 original 20 Hz history frames required")
    frames = []
    previous_frame = previous_time = None
    first_frame, first_time = rows[0].get("frame"), rows[0].get("time_s")
    for index, row in enumerate(rows):
        frame, time = row.get("frame"), row.get("time_s")
        if (not isinstance(frame, int) or isinstance(frame, bool) or
                frame != first_frame + index or
                not isinstance(time, (int, float)) or isinstance(time, bool) or
                not math.isfinite(time) or
                abs(time - first_time - index / 20) > 0.001 or
                (previous_frame is not None and frame != previous_frame + 1) or
                (previous_time is not None and abs(time - previous_time - 0.05) > 0.001)):
            raise ValueError("original 20 Hz frame join broken")
        if row.get("ego_actor_id") != spawned_actor_id or any(
                not isinstance(row.get(key), bool) for key in
                ("ego_body_in_intersection", "ego_body_in_designated_cycle_lane")):
            raise ValueError("original actor or body occupation missing")
        body = _polygon(row.get("ego_body_polygon"))
        if (row["ego_body_in_intersection"] != _intersects(body, intersection_polygon) or
                row["ego_body_in_designated_cycle_lane"] != _intersects(body, cycle_lane_polygon)):
            raise ValueError("original body occupation disagrees with source polygons")
        frames.append(frame)
        previous_frame, previous_time = frame, time
    cameras = seal.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four original camera views required")
    profile = seal.get("capture_profile")
    if (not isinstance(profile, dict) or profile.get("duration_s") != 45 or
            profile.get("hz") != 20 or profile.get("views") != list(VIEWS) or
            not isinstance(profile.get("controller_policy"), str) or
            not profile["controller_policy"]):
        raise ValueError("fixed 45-second four-camera capture profile required")
    for view, reference in cameras.items():
        if not isinstance(reference, dict) or not reference.get("path"):
            raise ValueError("original camera reference missing: " + view)
        path = root / reference["path"]
        if not path.resolve().is_relative_to(root) or _sha(path) != reference.get("sha256"):
            raise ValueError("original camera changed: " + view)
    overlap = sum(row["ego_body_in_intersection"] and row["ego_body_in_designated_cycle_lane"]
                  for row in rows)
    return {"format": "cycle-lane-source-measurement-v1", "case_id": case_id,
            "source_kind": "original_native", "site_sha256": reviewed_site_sha256,
            "subsection_3_sha256": reviewed_exception_sha256,
            "vehicle_sha256": reviewed_vehicle_sha256,
            "capture_profile_sha256": hashlib.sha256(json.dumps(
                profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "exception_clause_sha256": hashlib.sha256(
                exception["authoritative_clause"].encode()).hexdigest(),
            "attempt_source_sha256": _sha(root / "attempt-source.json"),
            "route_candidate_id": route["candidate_id"], "frame_count": len(frames),
            "intersection_frames": sum(row["ego_body_in_intersection"] for row in rows),
            "cycle_lane_frames": sum(row["ego_body_in_designated_cycle_lane"] for row in rows),
            "intersection_cycle_lane_overlap_frames": overlap,
            "subsection_3_status": exception["status"],
            "legal_verdict": None, "physical_acceptance_claimed": False}
