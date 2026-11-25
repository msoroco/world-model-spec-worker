"""Require reviewed source findings for each selected 257(1) yield branch.

The findings are preparation inputs. Actual motion and visible road markings
must still be checked against original Native capture before local acceptance.
"""
from __future__ import annotations

from build_semantic_proposals import KINDS, case_settings
from through_traffic_control import validate_plan as validate_through_plan


COMMON = ("yield_sign_governs_approach", "through_highway_confirmed",
          "no_officer_control", "no_signal_control")
REFERENCE_FINDINGS = {
    "nearest_view": ("no_marked_stop_line", "no_near_side_crosswalk",
                     "no_sidewalk_derived_crosswalk", "viewpoint_reviewed"),
    "marked_stop_line": ("marked_stop_line_present",),
    "near_side_marked_crosswalk": ("no_marked_stop_line",
                                  "near_side_marked_crosswalk_present"),
    "near_side_sidewalk_derived_crosswalk": ("no_marked_stop_line",
                                              "no_near_side_crosswalk",
                                              "sidewalk_derived_crosswalk_present"),
}
SURVEY_FOR_FINDING = {
    "yield_sign_governs_approach": "yield_sign",
    "through_highway_confirmed": "through_highway_survey",
    "no_officer_control": "control_survey",
    "no_signal_control": "control_survey",
    "no_marked_stop_line": "stop_line_survey",
    "marked_stop_line_present": "stop_line_survey",
    "no_near_side_crosswalk": "crosswalk_survey",
    "near_side_marked_crosswalk_present": "crosswalk_survey",
    "no_sidewalk_derived_crosswalk": "sidewalk_survey",
    "sidewalk_derived_crosswalk_present": "sidewalk_survey",
    "viewpoint_reviewed": "nearest_view_survey",
}


def validate_site_branch(site: dict, case_id: str) -> dict:
    kind = case_id.rsplit("__", 1)[-1]
    if kind not in KINDS:
        raise ValueError("unknown exact C158208 statutory case")
    settings = case_settings(kind)
    reference = next((key for key in REFERENCE_FINDINGS if kind.startswith(key)),
                     "nearest_view")
    context = site.get("reviewed_context")
    if not isinstance(context, dict):
        raise ValueError("reviewed branch context required")
    findings = COMMON + REFERENCE_FINDINGS[reference]
    for name in findings:
        if context.get(name) is not True:
            raise ValueError("reviewed statutory branch finding missing: " + name)
    incompatible = (("marked_stop_line_present", "no_marked_stop_line"),
                    ("near_side_marked_crosswalk_present", "no_near_side_crosswalk"),
                    ("sidewalk_derived_crosswalk_present", "no_sidewalk_derived_crosswalk"))
    if any(context.get(present) is True and context.get(absent) is True
           for present, absent in incompatible):
        raise ValueError("contradictory reviewed marking or sidewalk findings")
    cited = site.get("finding_sources")
    bindings = site.get("source_bindings")
    if not isinstance(cited, dict) or not isinstance(bindings, dict):
        raise ValueError("source-hashed branch finding references required")
    for name in findings:
        source = SURVEY_FOR_FINDING[name]
        if cited.get(name) != source or source not in bindings:
            raise ValueError("branch finding lacks matching original survey: " + name)
    planned = site.get("planned_through_traffic_phase")
    if planned != settings["through_traffic_phase"]:
        raise ValueError("reviewed through-traffic plan differs from exact case")
    if cited.get("planned_through_traffic_phase") != "through_highway_survey":
        raise ValueError("through-traffic phase lacks original survey plan")
    if site.get("planned_response_mode") != settings["response_mode"]:
        raise ValueError("reviewed response plan differs from exact case")
    native_scene = site.get("native_scene")
    if not isinstance(native_scene, dict) or not isinstance(native_scene.get("through_vehicle"), dict):
        raise ValueError("reviewed through-vehicle Native scene required")
    validate_through_plan(native_scene["through_vehicle"].get("motion_plan"))
    return {"case_id": case_id, "reference_branch": reference,
            "planned_response_mode": settings["response_mode"],
            "planned_through_traffic_phase": planned,
            "original_findings": list(findings)}
