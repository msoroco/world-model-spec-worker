"""Source-gated nighttime heavy-vehicle measurements without legal verdicts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

WEIGHT_LB = 8000
PERMITS = {"none", "valid", "application_only", "route_condition_breach", "time_condition_breach"}
STREETS = {"truck_route", "non_truck"}
DISTRICTS = {"residence", "nonresidence"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(value: dict, hashes: set[str], name: str) -> None:
    if value.get(name + "_source_sha256") not in hashes:
        raise ValueError("Original " + name + " source absent or unreviewed")


def load_review(path: Path, source_root: Path, case_id: str, diagnostic: bool = False) -> dict:
    """Check independent source bindings before any Native world mutation."""
    path, source_root = Path(path), Path(source_root)
    packet = json.loads(path.read_text())
    if packet.get("format") != "worker-reviewed-night-truck-site" or packet.get("case_id") != case_id:
        raise ValueError("Night truck review identity differs")
    if bool(packet.get("diagnostic_fixture")) != diagnostic:
        raise ValueError("Diagnostic night truck packet cannot become original evidence")
    provenance = packet.get("source_provenance", {})
    if not diagnostic and (provenance.get("kind") != "original_reviewed_site"
            or not provenance.get("reviewer") or not provenance.get("citation")):
        raise ValueError("Original night truck sources need independent reviewer and citation")
    files = provenance.get("files", [])
    if not files:
        raise ValueError("Original night truck source inventory missing")
    root = source_root.resolve()
    for item in files:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("Unversioned night truck source")
        target = (root / item["path"]).resolve()
        if root not in target.parents or not target.is_file() or sha(target) != item["sha256"]:
            raise ValueError("Original night truck source missing or changed")
    hashes = {item["sha256"] for item in files}
    site = packet.get("site", {})
    if site.get("municipal_jurisdiction_reviewed") is not True or site.get("chapter_scope_reviewed") is not True:
        raise ValueError("Municipal jurisdiction or chapter scope unreviewed")
    if site.get("district") not in DISTRICTS or site.get("frontage_reviewed") is not True or site.get("business_exclusion_reviewed") is not True:
        raise ValueError("Residence district frontage and business exclusion unreviewed")
    _source(site, hashes, "district")
    street = site.get("traveled_street", {})
    if type(street.get("road_id")) is not int or street.get("designation") not in STREETS:
        raise ValueError("Original traveled street identity/designation missing")
    _source(street, hashes, "designation")
    vehicle = packet.get("vehicle", {})
    if (type(vehicle.get("unladen_weight_lb")) not in (int, float)
            or not math.isfinite(vehicle["unladen_weight_lb"])
            or vehicle["unladen_weight_lb"] <= 0 or not vehicle.get("identity")
            or not str(vehicle.get("blueprint", "")).startswith("vehicle.")):
        raise ValueError("Vehicle-specific unladen weight or identity missing")
    _source(vehicle, hashes, "weight")
    clock = packet.get("civil_clock", {})
    _source(clock, hashes, "clock")
    if not clock.get("timezone") or not clock.get("start_utc") or clock.get("uncertainty_s") is None:
        raise ValueError("Original local civil time source missing")
    try:
        tz = ZoneInfo(clock["timezone"])
        start = datetime.fromisoformat(clock["start_utc"])
        if start.tzinfo is None or start.utcoffset() != timezone.utc.utcoffset(start):
            raise ValueError("Original start time must be UTC")
        local = start.astimezone(tz)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Original civil clock or timezone invalid") from error
    if type(clock["uncertainty_s"]) not in (int, float) or clock["uncertainty_s"] < 0:
        raise ValueError("Original clock uncertainty invalid")
    permit = packet.get("permit", {})
    if permit.get("status") not in PERMITS or permit.get("reviewed") is not True:
        raise ValueError("Written permit administrative review missing")
    _source(permit, hashes, "administrative")
    if permit["status"] in {"valid", "route_condition_breach", "time_condition_breach"}:
        if (permit.get("written_application") is not True or permit.get("issued_written_permit") is not True
                or not permit.get("applicant_id") or not permit.get("authorized_vehicle_identity")
                or not isinstance(permit.get("conditions"), list)
                or permit["authorized_vehicle_identity"] != vehicle["identity"]):
            raise ValueError("Issued written permit, scope or conditions missing")
    if permit["status"] in {"none", "application_only"}:
        if permit.get("issued_written_permit") is not False or permit.get("negative_search_reviewed") is not True:
            raise ValueError("Unissued permit requires reviewed administrative negative search")
    if permit["status"] == "application_only" and permit.get("written_application") is not True:
        raise ValueError("Application-only control lacks written application")
    itinerary = packet.get("itinerary", {})
    points = itinerary.get("waypoints_xy_m", [])
    spawn = itinerary.get("spawn_xyz_m", [])
    if len(points) < 2 or len(spawn) != 3:
        raise ValueError("Reviewed Native street itinerary missing")
    for point in points:
        if len(point) != 2 or not all(math.isfinite(float(v)) for v in point):
            raise ValueError("Reviewed itinerary waypoint invalid")
    if not all(math.isfinite(float(v)) for v in spawn):
        raise ValueError("Reviewed itinerary spawn invalid")
    packet["_derived_local_start"] = local.isoformat()
    return packet


def measure(source: Path) -> dict:
    """Measure source-bound original operation; keep endpoint/permit law unresolved."""
    packet = json.loads(Path(source).read_text())
    frames = packet.get("frames", [])
    if packet.get("fps") != 20 or len(frames) < 3 or not packet.get("case_id"):
        raise ValueError("Original nighttime operation frames missing")
    site = packet["site"]
    street = site["traveled_street"]
    prior_frame = -1
    prior_time = -1.0
    for row in frames:
        frame, time_s = row.get("frame"), row.get("time_s")
        if type(frame) is not int or frame <= prior_frame or type(time_s) not in (int, float) or time_s <= prior_time:
            raise ValueError("Original operation frame/time nonmonotonic")
        if (type(row.get("ego_actor_id")) is not int or row.get("road_id") != street["road_id"]
                or row.get("street_designation") != street["designation"]
                or row.get("vehicle_identity") != packet["vehicle"]["identity"]
                or len(row.get("position_xy_m", [])) != 2):
            raise ValueError("Original street or vehicle identity differs")
        prior_frame, prior_time = frame, time_s
    clock = packet["civil_clock"]
    start = datetime.fromisoformat(clock["start_utc"])
    local = start.astimezone(ZoneInfo(clock["timezone"]))
    return {
        "actual_unladen_weight_lb": packet["vehicle"]["unladen_weight_lb"],
        "weight_strictly_exceeds_8000": packet["vehicle"]["unladen_weight_lb"] > WEIGHT_LB,
        "local_civil_start": local.isoformat(),
        "local_civil_start_hhmm": local.strftime("%H:%M"),
        "clock_uncertainty_s": clock["uncertainty_s"],
        "district_reviewed_as": site["district"],
        "traveled_street_designation": street["designation"],
        "permit_review_status": packet["permit"]["status"],
        "permit_conditions": packet["permit"].get("conditions", []),
        "sample_count": len(frames),
        "first_native_frame": frames[0]["frame"],
        "last_native_frame": frames[-1]["frame"],
        "legal_time_endpoint_judgment": "unresolved",
        "legal_permit_effect_judgment": "unresolved"}
