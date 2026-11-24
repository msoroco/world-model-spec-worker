"""Independent saved-source officer exception comparison audit.

Run only after both exact attempts have original camera reviews. A passing
comparison describes observed source contrast, not a legal determination.
"""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("c157964_officer_measurements",
                                               ROOT / "officer_measurements.py")
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)

COMPARISONS = {
    "officer_exception_active": (
        MEASURE.PREFIX + "officer_active_stop_then_go", MEASURE.INACTIVE),
    "officer_direction": (
        MEASURE.PREFIX + "officer_active_stop_then_go",
        MEASURE.PREFIX + "officer_active_hold"),
}


def audit(comparison_id: str, first_root: Path, second_root: Path) -> dict:
    if comparison_id not in COMPARISONS:
        raise ValueError("Unknown exact officer comparison")
    first = MEASURE.analyze(Path(first_root))
    second = MEASURE.analyze(Path(second_root))
    if (first["case_id"], second["case_id"]) != COMPARISONS[comparison_id]:
        raise ValueError("Comparison exact case IDs differ from case plan")
    if first["fixed_context"] != second["fixed_context"]:
        raise ValueError("Comparison fixed intersection or ego-route context differs")
    left, right = first["first_ego_entry"], second["first_ego_entry"]
    if comparison_id == "officer_exception_active":
        if (left["traffic_control_observed"], right["traffic_control_observed"]) != (True, False):
            raise ValueError("Original officer-control contrast missing at ego entry")
        if not left["officer_visible"] or not right["officer_visible"]:
            raise ValueError("Both comparison officer appearances must be visible")
        if not any(row["direction"] == "stop" for row in first["samples"]):
            raise ValueError("Active officer stop phase not observed")
    else:
        if (left["traffic_control_observed"], right["traffic_control_observed"]) != (True, True):
            raise ValueError("Direction comparison lacks active control at ego entry")
        if left["officer_direction_observed"] != "go" or right["officer_direction_observed"] != "stop":
            raise ValueError("Original stop/go versus hold direction contrast missing")
        if (not any(row["direction"] == "stop" for row in first["samples"]) or
                any(row["direction"] != "stop" for row in second["samples"])):
            raise ValueError("Original direction histories do not show the planned contrast")
    return {"format": "worker-officer-control-comparison-audit",
            "comparison_id": comparison_id, "case_ids": list(COMPARISONS[comparison_id]),
            "fixed_context": first["fixed_context"],
            "source_hashes": {"first": first["sources"], "second": second["sources"]},
            "observed_at_entry": {"first": left, "second": right},
            "comparison_passed": True, "legal_conclusion": "unresolved",
            "physical_acceptance_claimed": False}
