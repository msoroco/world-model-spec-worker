"""Exact C153046 original-source recording channels for the draft cases."""
from __future__ import annotations

from build_case_plan import OBSERVATIONS


UNITS = {
    "official steady red alone": "categorical state",
    "antecedent stop location": "m",
    "complete stop": "m/s and s",
    "extreme left of one-way approach": "m and lane identity",
    "receiving one-way to left": "m and direction vector",
    "pedestrian right-of-way": "structured actor history",
    "other traffic right-of-way": "structured actor history",
    "yield response": "structured motion and control history",
}


def build() -> dict:
    return {"channels": [
        {"name": name, "unit": UNITS[name], "sampling_rate_hz": 20,
         "method": source,
         "time_window": "original approach through receiving-road exit",
         "reference_frame": "Native world frame/time joined to four original cameras",
         "uncertainty": "Original motion, aspect, participant right-of-way and pixels require physical review"}
        for name, source in OBSERVATIONS.items()],
        "context_inputs": [
            {"name": "reviewed_one_way_left_turn_site", "unit": "source record",
             "method": "SHA-256 retained OpenDRIVE and reviewed approach/receiving lane direction sources"},
            {"name": "reviewed_signal_and_stop_hierarchy", "unit": "source record",
             "method": "SHA-256 retained official signal and stop-boundary records"}],
        "limitations": [
            "A requested complete stop or yield does not establish its realized behavior.",
            "The frozen law supplies no numeric yielding or stopping duration threshold.",
            "Original camera pixels and source authority remain independently reviewable."]}
