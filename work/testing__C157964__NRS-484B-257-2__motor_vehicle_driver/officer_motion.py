"""Saved-only original actor/gesture measurements for NRS 484B.257(2).

Engineering observations remain separate from the officer-control legal exception
and any judgment of an immediate hazard or cautious driving.
"""

from __future__ import annotations

from math import isfinite
from typing import Mapping

from officer_scene import CASES, Case, validate_site


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def measure(rows: list[Mapping], site: Mapping, case: Case,
            diagnostic_fixture: bool = False) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact officer case")
    scene = validate_site(site)
    required_count = (8 <= len(rows) <= 20 or len(rows) == 900) if diagnostic_fixture and isinstance(rows, list) else len(rows) == 900 if isinstance(rows, list) else False
    if not required_count:
        raise ValueError("complete original 900-frame Native history required")
    first_frame = rows[0].get("frame")
    first_time = rows[0].get("time_s")
    if type(first_frame) is not int or not _number(first_time):
        raise ValueError("original frame/time missing")
    ego_id = other_id = officer_id = None
    entry = None
    speeds = []
    phases = []
    directives = []
    crossing = []
    for index, row in enumerate(rows):
        if row.get("frame") != first_frame + index or \
                not _number(row.get("time_s")) or \
                abs(row["time_s"] - first_time - index / 20) > .005:
            raise ValueError("original officer frame/time history has a gap")
        state = row.get("state")
        if not isinstance(state, dict):
            raise ValueError("original actor state missing")
        ego = state.get("ego")
        other = state.get("other")
        officer = state.get("officer")
        if not all(isinstance(x, dict) for x in (ego, other, officer)):
            raise ValueError("original ego/other/officer state missing")
        ids = (ego.get("id"), other.get("id"), officer.get("id"))
        if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != 3:
            raise ValueError("original participant identity missing")
        if index == 0:
            ego_id, other_id, officer_id = ids
        elif ids != (ego_id, other_id, officer_id):
            raise ValueError("original participant identity changed")
        speed = ego.get("speed_mps")
        station = ego.get("leading_station_m")
        other_station = other.get("center_station_m")
        if not all(_number(x) for x in (speed, station, other_station)):
            raise ValueError("original ego/other motion missing")
        phase = other.get("phase")
        if phase not in ("approaching", "within", "cleared"):
            raise ValueError("original other phase missing")
        if officer.get("controls_traffic") is not True or \
                officer.get("visible") is not True:
            raise ValueError("original active officer/visibility missing")
        directive = state.get("officer_directive")
        if directive not in ("stop", "proceed") or \
                directive != officer.get("directive"):
            raise ValueError("original officer directive/readback missing")
        if type(ego.get("across_or_within")) is not bool:
            raise ValueError("original crossing history missing")
        if entry is None and station >= scene["intersection_entry_station_m"]:
            entry = index
        speeds.append(speed)
        phases.append((phase, other_station))
        directives.append(directive)
        crossing.append(ego["across_or_within"])
    if entry is None or entry == 0 or \
            rows[entry - 1]["state"]["ego"]["leading_station_m"] >= \
            scene["intersection_entry_station_m"]:
        raise ValueError("first original leading-body entry missing")
    if not any(crossing[entry:]):
        raise ValueError("original across-or-within history absent")
    if phases[entry][0] != case.other_phase:
        raise ValueError("requested other phase not physically realized at entry")
    if directives[entry] != case.officer_directive:
        raise ValueError("requested officer directive not observed at entry")
    return {"case_suffix": case.suffix, "frame_count": len(rows),
            "first_original_entry_frame": first_frame + entry,
            "observed_officer_directive_at_entry": directives[entry],
            "observed_other_phase_at_entry": phases[entry][0],
            "observed_other_center_station_at_entry_m": phases[entry][1],
            "minimum_original_ego_speed_before_entry_mps": min(speeds[:entry + 1]),
            "officer_control_context": "observed_active_visible_in_native",
            "independent_video_review": "pending",
            "immediate_hazard_judgment": None,
            "cautious_proceeding_judgment": None,
            "legal_judgment": None}
