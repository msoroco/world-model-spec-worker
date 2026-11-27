"""Expand the frozen lighting law into source-grounded test cases.

Engineering beam requests and distances are construction variables. They are
never substituted for physical glare, safe illumination, or a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = "testing__C230259__NRS-484D-215-1__motor_vehicle_driver"
INPUT = REPO / "inputs" / ASSIGNMENT
SOURCE = "NRS 484D.215(1)"


def source(path: Path) -> dict:
    return {"path": path.relative_to(REPO).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> dict:
    frozen = json.loads((INPUT / "assignment.json").read_text())
    current = json.loads((ROOT / "case-plan.json").read_text())
    if frozen["assignment_id"] != ASSIGNMENT or frozen["law"]["id"] != "NRS-484D-215-1":
        raise ValueError("frozen identity differs")
    gap = "no-accepted-original-recording"
    # A distance case requests a starting separation. Measured Native body gap
    # and eye-to-eye separation decide which original frames are in the 500 ft
    # window. The low beam name is an API request, not the statutory definition.
    variants = [
        ("general_high", "general", "high", None, "level", "standard"),
        ("general_low", "general", "low", None, "level", "standard"),
        ("general_dark", "general", "off", None, "level", "standard"),
        ("oncoming_499_high", "oncoming", "high", 499, "level", "standard"),
        ("oncoming_499_low", "oncoming", "low", 499, "level", "standard"),
        ("oncoming_500_low", "oncoming", "low", 500, "level", "standard"),
        ("oncoming_501_low", "oncoming", "low", 501, "level", "standard"),
        ("oncoming_499_low_crest_loaded", "oncoming", "low", 499, "crest", "loaded"),
    ]
    cases = []
    for suffix, branch, beam, feet, contour, load in variants:
        cases.append({
            "case_id": ASSIGNMENT + "__" + suffix,
            "kind": "delivery", "target_law_id": frozen["law_id"],
            "gap_ids": [gap], "branch": branch,
            "requested_beam": beam, "requested_start_separation_ft": feet,
            "requested_contour": contour, "requested_load": load,
            "physical_status": "unverified",
            "physical_risk": "Actual beam distribution, eye glare, person and vehicle visibility and Native motion require original pixels and photometric review.",
            "legal_judgment": "unresolved",
        })
    by_suffix = {x["case_id"].removeprefix(ASSIGNMENT + "__"): x["case_id"] for x in cases}
    fixed = ["C230259 source-reviewed road and opposing routes", "motor vehicle blueprint and driver", "night lighting-time packet", "45 s at 20 Hz and four synchronized cameras", "person and target vehicle placement", "original eye/beam measurement method"]
    pairs = [
        ("general_beam_distribution", "general_high", "general_low", ["requested high versus low distribution"]),
        ("general_no_distribution", "general_low", "general_dark", ["requested low versus off distribution"]),
        ("near_oncoming_glare", "oncoming_499_high", "oncoming_499_low", ["requested high versus low distribution"]),
        ("five_hundred_feet_lower", "oncoming_499_low", "oncoming_500_low", ["requested start separation 499 versus 500 feet"]),
        ("five_hundred_feet_upper", "oncoming_500_low", "oncoming_501_low", ["requested start separation 500 versus 501 feet"]),
        ("lowermost_contour_load", "oncoming_499_low", "oncoming_499_low_crest_loaded", ["source-reviewed level versus crest contour", "standard versus loaded vehicle configuration"]),
    ]
    current["cases"] = cases
    current["comparisons"] = [{"comparison_id": name, "case_ids": [by_suffix[a], by_suffix[b]], "fixed_conditions": fixed, "deliberate_differences": diffs} for name, a, b, diffs in pairs]
    current["evidence_review"] = {"reviewer": "CPU worker", "method": "Reviewed frozen evidence.json and exact law text. The inventory has no accepted recordings or source media; no physical equivalence can be established.", "facts": [], "gaps": [{"id": gap, "requirement": "Qualifying motion/time, illumination of persons and vehicles ahead, measured oncoming 500-foot condition, actual eye glare, and lowermost distribution require original evidence.", "source": source(INPUT / "assignment.json"), "why_existing_insufficient": "Frozen evidence inventory contains zero accepted recordings and no original Native or pixel source."}]}
    current["observations"] = [
        {"name": "qualifying_location_and_time", "source": "original source-reviewed highway polygon, road/shoulder footprints, calendar clock, sunset/sunrise or 1,000-foot visibility/device packet", "mandatory": True},
        {"name": "actor_motion_and_separation", "source": "20 Hz original ego, oncoming and target body/eye positions with frame joins", "mandatory": True},
        {"name": "beam_command_and_readback", "source": "20 Hz original ego light-state command/readback plus mounted lamp pose", "mandatory": True},
        {"name": "beam_and_glare_pixels", "source": "four original camera PNG streams, exposure/calibration and reviewed eye-target ROI", "mandatory": True},
        {"name": "road_contour_and_load", "source": "source-reviewed road elevation profile, vehicle load and lamp orientation", "mandatory": True},
    ]
    names = [x["case_id"] for x in cases]
    current["requirement_dispositions"] = [
        {"disposition_index": i, "requirement": requirement, "source": SOURCE, "status": "selected_required", "case_ids": case_ids, "evidence_or_gap": gap}
        for i, (requirement, case_ids) in enumerate([
            ("motor vehicle operated on traveled highway or adjacent shoulder during NRS 484D.100 times", names),
            ("distribution high and intense enough to reveal persons and vehicles a safe distance ahead", names),
            ("oncoming approach within 500 feet, measured from original geometry", [x for x in names if "oncoming" in x]),
            ("glaring rays not projected into eyes of oncoming driver", [x for x in names if "oncoming" in x]),
            ("lowermost distribution per NRS 484D.210(2), including contour and load", [x for x in names if "low" in x]),
        ])
    ]
    current["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45, "fps": 20, "composition": "synchronized_four_view_primary", "coverage": [
        {"view": "overview", "interval": "all 900 frames", "subject": "ego/oncoming bodies, highway and sampled 500-foot approach"},
        {"view": "approach", "interval": "all 900 frames", "subject": "person and vehicle ahead, physical road illumination"},
        {"view": "reference_corner", "interval": "all 900 frames", "subject": "contour, original body/eye positions and lamp installation"},
        {"view": "driver_reference", "interval": "all 900 frames", "subject": "original oncoming driver-eye region and glare rays"},
    ]}
    current["source_observation_mapping"] = {}
    current["planning_status"] = "exact_cases_with_source_requirements"
    current["runtime_uncertainties"] = ["CARLA light-state bits do not prove emitted beam distribution or lowermost statutory specification.", "No numerical legal safe-distance or glare threshold is supplied.", "The 500-foot condition must be measured on original source geometry, including endpoint ambiguity; requested start distance is not evidence.", "Physical realization and camera visibility remain for later original-source review."]
    return current


if __name__ == "__main__":
    (ROOT / "case-plan.json").write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
