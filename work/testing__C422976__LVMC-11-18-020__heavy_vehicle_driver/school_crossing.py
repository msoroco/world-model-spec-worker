"""Source-gated school-crossing geometry and original-frame measurements.

The measurements describe a recording. They do not decide whether a person
was legally attempting to cross or interpret the approaching-side phrase.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C422976__LVMC-11-18-020__heavy_vehicle_driver"
LAW = "LVMC-11-18-020"
SOURCES = ("municipal_authority", "crossing_geometry", "sign_installation",
           "vehicle_classification", "pedestrian_source")


@dataclass(frozen=True)
class Case:
    name: str
    sign_distance_ft: float
    sign_displayed: bool
    person_side: str
    person_attempt: bool
    entry_requested: bool
    crossing_marking: str = "yellow_paint"
    sign_placement: str = "curb"


CASES = (
    Case("near_attempt_hold", 100.0, True, "approach_side", True, False),
    Case("near_attempt_enter", 100.0, True, "approach_side", True, True),
    Case("near_presence_enter", 100.0, True, "approach_side", False, True),
    Case("far_attempt_enter", 100.0, True, "opposite_side", True, True),
    Case("sign_99ft_enter", 99.0, True, "approach_side", True, True),
    Case("sign_101ft_enter", 101.0, True, "approach_side", True, True),
    Case("no_display_enter", 100.0, False, "approach_side", True, True),
    Case("buttons_pavement_enter", 100.0, True, "approach_side", True, True,
         "road_buttons", "pavement"),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _point(value, label: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2,
            "missing two-dimensional point: " + label)
    point = (float(value[0]), float(value[1]))
    require(all(math.isfinite(x) for x in point), "nonfinite point: " + label)
    return point


def _rect(value, label: str) -> tuple[float, float, float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 4,
            "missing rectangle: " + label)
    rect = tuple(float(x) for x in value)
    require(all(math.isfinite(x) for x in rect) and
            rect[0] < rect[2] and rect[1] < rect[3],
            "invalid rectangle: " + label)
    return rect


def source_site(site: dict, site_path: str | Path, site_sha256: str,
                *, case: Case, native_readback: dict | None = None) -> None:
    """Check independent source bytes and a Native infrastructure readback."""
    path = Path(site_path)
    require(sha(path.read_bytes()) == site_sha256, "reviewed site seal mismatch")
    require(site.get("assignment_id") == ASSIGNMENT and
            site.get("source_kind") == "reviewed_original_native_school_crossing",
            "reviewed site identity mismatch")
    require(site.get("cell_id") == "C422976" and
            site.get("catalog_control") == "school_crosswalk" and
            site.get("law_id") == LAW, "frozen cell or law mismatch")
    require(site.get("case_ids") == [ASSIGNMENT + "__" + c.name for c in CASES],
            "exact case inventory mismatch")
    records = site.get("source_records")
    require(isinstance(records, dict) and set(SOURCES) <= set(records),
            "independent source records missing")
    for name in SOURCES:
        entry = records[name]
        require(isinstance(entry, dict) and isinstance(entry.get("path"), str) and
                isinstance(entry.get("sha256"), str) and len(entry["sha256"]) == 64,
                "source record incomplete: " + name)
        relative = Path(entry["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,
                "source path escapes site: " + name)
        require(sha((path.parent / relative).read_bytes()) == entry["sha256"],
                "source bytes changed: " + name)
    require(site.get("jurisdiction") == "Las Vegas municipal",
            "municipal jurisdiction unreviewed")
    require(site.get("engineer_opinion_source") and site.get("sign_necessity_source"),
            "engineer opinion and necessity source missing")
    require(site.get("operator_id") and site.get("vehicle_id") and
            site.get("vehicle_class") == "heavy_vehicle", "driver or heavy vehicle unreviewed")
    require(site.get("route_clearance_reviewed") is True,
            "heavy-vehicle route clearance unreviewed")
    require(site.get("intersection_status") == "intersection" and
            site.get("school_vicinity_reviewed") is True,
            "school intersection context unreviewed")
    crossing = _rect(site.get("crossing_rect_m"), "crossing")
    _rect(site.get("roadway_rect_m"), "roadway")
    width = float(site.get("crossing_width_ft"))
    require(math.isfinite(width) and width > 0, "crossing width unmeasured")
    require(site.get("crossing_marking") == case.crossing_marking,
            "statutory crossing marking differs from case")
    sign = site.get("sign")
    require(isinstance(sign, dict) and sign.get("words") == "School-Xing" and
            sign.get("conspicuous_reviewed") is True,
            "exact conspicuous School-Xing sign unreviewed")
    require(sign.get("placement") == case.sign_placement,
            "sign placement differs from case")
    require(abs(float(sign.get("advance_distance_ft")) - case.sign_distance_ft) < 0.25,
            "sign advance distance differs from case")
    require(sign.get("displayed") is case.sign_displayed,
            "actual sign display differs from case")
    person = site.get("person")
    require(isinstance(person, dict) and person.get("id") and
            person.get("side_relative_to_approach") == case.person_side and
            person.get("attempt_evidence_source") and
            person.get("attempt_requested") is case.person_attempt,
            "person side or attempting evidence unreviewed")
    _point(site.get("approach_direction_xy"), "approach direction")
    _point(site.get("opposing_direction_xy"), "opposing direction")
    require(site.get("road_id") is not None and site.get("lane_id") is not None,
            "approach lane unreviewed")
    require(site.get("map_sha256") and site.get("crossing_id") and
            site.get("sign_id"), "Native infrastructure identity missing")
    if native_readback is not None:
        for key in ("crossing_id", "crossing_rect_m", "roadway_rect_m",
                    "crossing_width_ft", "crossing_marking", "sign_id",
                    "road_id", "lane_id"):
            require(native_readback.get(key) == site.get(key),
                    "Native infrastructure readback mismatch: " + key)
        require(native_readback.get("sign") == site["sign"],
                "Native School-Xing display readback mismatch")
    require(crossing[2] - crossing[0] > 0, "crossing has no physical area")


def _inside(point: tuple[float, float], rect: tuple[float, float, float, float]) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def measure_original(rows: list[dict], site: dict, case: Case) -> dict:
    """Measure crossing entry and person state from synchronized original rows."""
    require(rows and all(isinstance(row, dict) for row in rows),
            "original synchronized history missing")
    crossing = _rect(site["crossing_rect_m"], "crossing")
    roadway = _rect(site["roadway_rect_m"], "roadway")
    previous_frame = None
    entry = None
    samples = []
    for row in rows:
        frame = row.get("source_frame_id")
        require(type(frame) is int and
                (previous_frame is None or frame == previous_frame + 1),
                "original frame sequence discontinuity")
        previous_frame = frame
        require(row.get("actor_id") == site["vehicle_id"] and
                row.get("person_id") == site["person"]["id"],
                "participant identity changed")
        require(row.get("road_id") == site["road_id"] and
                row.get("lane_id") == site["lane_id"],
                "approach lane changed")
        front = _point(row.get("vehicle_front_xy"), "vehicle front")
        person = _point(row.get("person_xy"), "person")
        in_crossing = _inside(front, crossing)
        person_in_crossing = _inside(person, crossing) and _inside(person, roadway)
        require(row.get("sign_displayed") is case.sign_displayed,
                "sign display changed during capture")
        require(row.get("person_attempt_source_sha256") ==
                site["source_records"]["pedestrian_source"]["sha256"],
                "person attempt source changed")
        attempt_observed = row.get("person_attempt_observed")
        require(type(attempt_observed) is bool, "person attempt observation missing")
        if in_crossing and entry is None:
            entry = {"frame": frame, "time_s": float(row["time_s"]),
                     "person_in_crossing": person_in_crossing,
                     "person_attempt_observed": attempt_observed,
                     "person_side_relative_to_approach": row.get("person_side_relative_to_approach")}
        samples.append({"frame": frame, "time_s": float(row["time_s"]),
                        "vehicle_front_xy": list(front), "person_xy": list(person),
                        "vehicle_in_crossing": in_crossing,
                        "person_in_crossing": person_in_crossing,
                        "person_attempt_observed": attempt_observed,
                        "person_side_relative_to_approach": row.get("person_side_relative_to_approach")})
    return {"case_id": ASSIGNMENT + "__" + case.name,
            "source_kind": "original_native" if rows[0].get("native_source") else "diagnostic_fixture",
            "crossing_width_ft_measured": float(site["crossing_width_ft"]),
            "sign_advance_distance_ft_measured": float(site["sign"]["advance_distance_ft"]),
            "sign_displayed_at_entry": case.sign_displayed if entry else None,
            "entry": entry, "samples": samples,
            "legal_approaching_side_unresolved": True,
            "engineer_opinion_not_inferred_from_pixels": True}


def load_site(path: str | Path, expected_sha256: str, case: Case,
              native_readback: dict | None = None) -> dict:
    path = Path(path)
    site = json.loads(path.read_text())
    source_site(site, path, expected_sha256, case=case, native_readback=native_readback)
    return site
