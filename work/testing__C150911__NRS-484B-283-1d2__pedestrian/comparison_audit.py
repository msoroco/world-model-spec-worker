"""Independent paired-attempt audit of fixed context and declared differences."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery

ASSIGNMENT = "testing__C150911__NRS-484B-283-1d2__pedestrian"
PAIRS = {
    "completion_before_at": ("before_zero_dont_walk", "at_zero_dont_walk"),
    "completion_at_after": ("at_zero_dont_walk", "after_zero_dont_walk"),
    "word_wait": ("before_zero_dont_walk", "before_zero_wait"),
    "hand_symbol": ("before_zero_dont_walk", "before_zero_hand"),
    "crossing_direction": ("before_zero_dont_walk", "before_zero_reverse"),
}


def load(attempt: Path) -> tuple[dict, dict]:
    if not (attempt / "original-countdown-observations.json").is_file():
        raise ValueError("Missing required source: original-countdown-observations.json")
    config = json.loads((attempt / "config.json").read_text())
    packet = json.loads((attempt / "original-countdown-observations.json").read_text())
    return config, packet


def compare(comparison: str, first_attempt: Path, second_attempt: Path,
            diagnostic: bool = False) -> dict:
    if comparison not in PAIRS:
        raise ValueError("unknown countdown comparison")
    first_attempt, second_attempt = first_attempt.resolve(), second_attempt.resolve()
    c1, p1 = load(first_attempt)
    c2, p2 = load(second_attempt)
    id1, id2 = c1.get("selected_case_id"), c2.get("selected_case_id")
    suffixes = (id1.rsplit("__", 1)[-1], id2.rsplit("__", 1)[-1])
    if (id1 == id2 or any(not x.startswith(ASSIGNMENT + "__") for x in (id1, id2)) or
            not set(suffixes) <= set(PAIRS[comparison])):
        raise ValueError("comparison exact cases differ from declared pair")
    common = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
        "required_atoms", "source_packets", "physical_completion")
    for key in common:
        if c1.get(key) != c2.get(key):
            raise ValueError("comparison fixed configuration differs: " + key)
    s1, s2 = p1.get("site", {}), p2.get("site", {})
    for key in ("layout", "opendrive_source_sha256", "highway_source_sha256",
                "highway_polygon_xy", "signal_source_sha256",
                "signal_facing_source_sha256", "one_way_direction_source_sha256",
                "exception_context_source_sha256"):
        if s1.get(key) is None or s1.get(key) != s2.get(key):
            raise ValueError("comparison fixed original site differs: " + key)
    a1 = audit_delivery(first_attempt, id1, diagnostic)
    a2 = audit_delivery(second_attempt, id2, diagnostic)
    if a1["first_zero_original_frame"] != a2["first_zero_original_frame"]:
        raise ValueError("comparison original countdown zero frame differs")
    if comparison in ("completion_before_at", "completion_at_after"):
        if (p1["frames"][0]["signal_form"] != p2["frames"][0]["signal_form"] or
                a1["completion_relation"] == a2["completion_relation"]):
            raise ValueError("completion boundary difference not isolated")
    elif comparison in ("word_wait", "hand_symbol"):
        if (p1["frames"][0]["signal_form"] == p2["frames"][0]["signal_form"] or
                a1["completion_relation"] != a2["completion_relation"]):
            raise ValueError("signal form difference not isolated")
    elif comparison == "crossing_direction":
        if (p1["frames"][0]["signal_facing_direction"] ==
                p2["frames"][0]["signal_facing_direction"] or
                a1["completion_relation"] != a2["completion_relation"]):
            raise ValueError("crossing direction difference not isolated")
    return {"format": "worker-independent-countdown-comparison",
        "assignment_id": ASSIGNMENT, "comparison_id": comparison,
        "case_ids": [id1, id2], "passed": True,
        "fixed_original_site_sha256": s1["highway_source_sha256"],
        "first_zero_original_frame": a1["first_zero_original_frame"],
        "deliberate_differences": {
            "completion_relation": [a1["completion_relation"], a2["completion_relation"]],
            "signal_form": [p1["frames"][0]["signal_form"], p2["frames"][0]["signal_form"]],
            "direction": [p1["frames"][0]["signal_facing_direction"],
                p2["frames"][0]["signal_facing_direction"]]},
        "physical_acceptance": False, "legal_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = compare(args.comparison, args.first_attempt,
        args.second_attempt, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "passed": True}))


if __name__ == "__main__":
    main()
