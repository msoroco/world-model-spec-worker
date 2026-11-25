"""Build source-hashed draft semantic stages for the two exact selected cases.

This is a physical measurement plan. It does not decide right of way or the
applicability of subsection 4 at the inoperative signal.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = "NRS-484B-250-1"
ACTOR = "motor_vehicle_driver"
CELL = "C125697"
TEMPLATE = LAW + "@" + ACTOR


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recording_description() -> dict:
    return {
        "channels": [
            {"name": "intersection_body_history", "unit": "native record",
             "sampling_rate_hz": 20,
             "method": "original synchronized actor IDs, road IDs and four-corner body footprints",
             "time_window": "all 900 original frames", "reference_frame": "reviewed roadway crossing bounds",
             "uncertainty": "original site and realized motion remain unreviewed"},
            {"name": "governing_signal_readback", "unit": "native record",
             "sampling_rate_hz": 20,
             "method": "original governing signal readback joined to Native frame and elapsed clock",
             "time_window": "all 900 original frames", "reference_frame": "identified crossing approaches",
             "uncertainty": "governing device and subsection 4 applicability remain unreviewed"},
        ],
        "context_inputs": [
            {"name": "reviewed_site_device_highway_packet", "unit": "source",
             "method": "source-hashed original OpenDRIVE, public-highway and official-device records"},
            {"name": "approach_and_turn_intent", "unit": "source",
             "method": "source-hashed route geometry and original actor heading histories"},
        ],
        "limitations": [
            "A diagnostic source packet cannot establish a legal right-of-way judgment.",
            "An inoperative signal alone does not establish whether subsection 4 overrides the official-device exclusion.",
            "Original body motion and four-camera physical visibility remain unreviewed.",
        ],
    }


def judgment(phrase: str, note: str, names: list[str]) -> dict:
    observable = [
        {"name": name, "unit": "native record",
         "description": "Original synchronized body or governing-device history for " + phrase + "."}
        for name in names
    ]
    return {
        "template_id": TEMPLATE, "phrase": phrase, "note": note, "status": "draft",
        "observable_requirements": {
            "observables": observable,
            "context_inputs": [
                {"name": "reviewed_site_device_highway_packet", "unit": "source",
                 "description": "Original reviewed roadway, highway and device source provenance."},
                {"name": "approach_and_turn_intent", "unit": "source",
                 "description": "Original route and actor heading history for the opposing-turn exclusion."},
            ],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": observable,
            "limitations": ["This measured history is not a statutory legal cutoff or applicability verdict."],
        },
    }


def build() -> None:
    assignment_path = Path("inputs") / AID / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    law_text = assignment["law"]["text"]
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    description = recording_description()
    for case in plan["cases"]:
        case["recording_description"] = description
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "sampling_rate_hz": 20,
        "duration_s": 45, "frame_count": 900,
        "views": ["front", "rear", "left", "right"],
        "physical_pixels_verified": False,
    }
    plan["source_observation_mapping"] = {}
    plan["requirement_dispositions"] = [
        {"disposition_index": i, "requirement": req, "status": "selected_required",
         "source": {"path": str(assignment_path), "sha256": digest(assignment_path)},
         "evidence_or_gap": "Selected exact-case source audit is authored; original roadway and actor sources are pending.",
         "case_ids": [c["case_id"] for c in plan["cases"]],
         "reason": reason}
        for i, (req, reason) in enumerate([
            ("identified intersection and different public highways", "Both approach road and highway source records must be checked against original OpenDRIVE."),
            ("other vehicle enters before ego", "Original footprint entry transitions and Native clock establish order."),
            ("ego response relative to other exit", "Original footprint exit and ego entry transitions distinguish the controlled pair."),
            ("official-device and subsection 4 applicability", "Original governing-device record and separate subsection 4 review remain necessary."),
            ("opposite-direction left-turn exclusion", "Original approach geometry and turn intent must rule out this exclusion."),
        ])
    ]
    write(plan_path, plan)

    relevance = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": law_text, "applies_to": [ACTOR],
                           "relevance_type": "conditional earlier intersection entry from a different highway",
                           "confidence": "low",
                           "notes": "The fixed inoperative official signal requires source review of subsection 4 applicability."}],
        "borderline_excluded": [],
    }
    clause = law_text.split("Except as otherwise provided", 1)[1]
    exception = "Except as otherwise provided" + clause
    phrases = [
        ("intersection", "Identify the same physical roadway crossing for both vehicles; a median opening label alone is insufficient.", ["intersection_body_history"]),
        ("different highway", "Review original road and public-highway identity sources for both approaches.", ["intersection_body_history"]),
        ("entered the intersection", "Use original footprint transitions with an uninterrupted Native frame clock.", ["intersection_body_history"]),
        ("intersections controlled by official traffic-control devices", "Review the governing device and subsection 4 separately; inoperative readback is not an applicability ruling.", ["governing_signal_readback"]),
        ("approaching each other from opposite directions", "Review original approach trajectories and left-turn intent for the statutory exclusion.", ["intersection_body_history"]),
    ]
    template = {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "quote": law_text,
        "structure": {
            "law_id": LAW,
            "activation": {"condition": "An ego driver approaches an intersection after another vehicle entered it from a different highway.", "numeric_conditions": []},
            "obligation": {"description": "Yield right-of-way to the already-entered vehicle if subsection 1 applies.", "type": "must", "numeric_conditions": []},
            "exceptions": [{"source_clause": exception,
                            "description": "Official control, opposing left-turn context and subsection 4 qualification require independent review."}],
            "timing": {"description": "Measure original body entry and exit transitions and preserve their 20 Hz sample brackets.", "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": p, "note": n} for p, n, _ in phrases],
        },
        "parameter_refs": [{"name": "ego_response_request", "kind": "controller",
                            "range_or_domain": "yield_before_entry or advance_before_other_exit; requested behavior is not measured behavior"}],
    }
    bindings = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": ["Frozen cell C125697 is median opening, travel, inoperative signal; original site and device sources are unreviewed."],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "median_crossing_site", "value": "original_source_pending",
                              "rationale": "The same inspected roadway, highway and device sources must be held fixed."}],
        "variable_parameters": [{"name": "ego_response_request", "kind": "controller",
                                 "range_or_domain": "yield_before_entry or advance_before_other_exit",
                                 "used_by_laws": [LAW]}],
    }
    semantic_cases = []
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        response = "yield_before_entry" if suffix == "precedence" else "advance_before_other_exit"
        semantic_cases.append({
            "case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe",
            "rationale": "Controlled requested response contrast; observed entry and exit order is measured, not presumed.",
            "variable_assignments": {"ego_response_request": {"kind": "controller", "value": response}},
            "paired_probe_id": "inoperative_signal_precedence",
            "deliberate_differences": ["ego_response_request"],
            "probe": {"primary_variable": "ego_response_request",
                      "comparison_or_standard": "original body entry relative to other exit",
                      "target_value_or_branch": suffix},
            "unresolved_judgment_calls": [p for p, _, _ in phrases],
            "recording_description": description,
        })
    semantic_cases.append({
        "case_id": AID + "__semantic_baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Semantic reference only; no extra recording.",
        "variable_assignments": {"ego_response_request": {"kind": "controller", "value": "yield_before_entry"}},
        "deliberate_differences": [], "unresolved_judgment_calls": [p for p, _, _ in phrases],
        "recording_description": description,
    })
    cases = {
        "cell_id": CELL, "actor": ACTOR, "status": "draft", "sweeps_expanded": True,
        "sweep_specs": [{"sweep_id": f"c125697-judgment-{i}", "target_law_id": LAW,
                         "status": "incomplete", "judgment_refs": [{"phrase": p, "note": n}],
                         "rationale": "Original reviewed roadway, device and actor histories are absent; no legal boundary is inferred.",
                         "missing_inputs": ["reviewed original site/device packet and accepted original actor histories"]}
                        for i, (p, n, _) in enumerate(phrases, 1)],
        "cases": semantic_cases,
    }
    stages = {"relevance_batch": relevance, "relevance": relevance,
              "template": template, "bindings": bindings, "cases": cases}
    refs = {}
    for name, body in stages.items():
        path = HERE / "proposals" / (name + ".json")
        write(path, body)
        refs[name] = {"path": str(path.relative_to(HERE)), "sha256": digest(path)}
    observed = []
    for i, (phrase, note, names) in enumerate(phrases, 1):
        path = HERE / "proposals" / (f"judgment-{i}.json")
        write(path, judgment(phrase, note, names))
        observed.append({"path": str(path.relative_to(HERE)), "sha256": digest(path)})
    refs["judgment_observables"] = observed
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "source": {"path": str(assignment_path), "sha256": digest(assignment_path)},
             "stages": refs, "status": "draft_local_source_and_physical_review_pending"}
    write(HERE / "proposals" / "semantic-index.json", index)
    print("built canonical draft semantic stages for two exact selected cases")


if __name__ == "__main__":
    build()
