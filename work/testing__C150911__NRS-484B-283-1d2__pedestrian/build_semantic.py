"""Draft canonical semantic stages for source-bound flashing countdown crossing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "proposals"
LAW = "NRS-484B-283-1d2"
ACTOR = "pedestrian"
TEMPLATE = LAW + "@" + ACTOR


def write(name: str, value: dict) -> dict:
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
        ensure_ascii=False) + "\n")
    return {"path": str(path.relative_to(HERE)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def recording_description() -> dict:
    channels = []
    for name, unit, method in (
        ("signal_countdown", "indication and integer", "same-frame facing official signal form, illumination, flashing and legible countdown value"),
        ("pedestrian_crossing", "position", "original pedestrian pose and highway entry/completion boundary"),
        ("highway_context", "source", "source-hashed one-way public highway, both crossing directions and crosswalk"),
        ("exception_context", "inventory", "original context for cited NRS 484B.287, .290 and .350")):
        channels.append({"name": name, "unit": unit, "sampling_rate_hz": 20,
            "method": method, "time_window": "900 original frames",
            "reference_frame": "original signal, pedestrian and one-way highway",
            "uncertainty": "actual Native source and visible pixels pending"})
    return {"channels": channels, "context_inputs": [{"name": "reviewed_countdown_site",
        "unit": "source", "method": "original OpenDRIVE, highway, crossing, official facing signal and exception source hashes"}],
        "limitations": ["Requested countdown and speed do not establish actual display or crossing completion.",
            "Referenced exceptions remain unresolved for independent review."]}


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": "C150911", "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low",
        "relevance_type": "specific_match",
        "notes": "Original illuminated flashing indication, legible countdown and crossing completion relative to zero require source-bound measurement."}],
        borderline_excluded=[])
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    variables = [("signal_form", "Don't Walk, Wait or upraised hand"),
        ("direction", "forward or reverse governed pedestrian crossing"),
        ("completion", "before, at or after displayed zero")]
    template_ref = write("template.json", {"status": "draft", "law_id": LAW,
        "actor": ACTOR, "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": name, "kind": "world_setup",
            "range_or_domain": domain} for name, domain in variables],
        "structure": {"activation": {"condition": "A facing pedestrian Don't Walk, Wait or upraised hand indication is illuminated and flashing with a countdown timer.",
            "numeric_conditions": []},
            "obligation": {"type": "may_with_completion_condition",
                "description": quote,
                "numeric_conditions": [{"measure": "first displayed zero versus complete highway crossing", "operator": "before", "unit": "original frame"}]},
            "exceptions": [{"source_clause": item,
                "status": "applicability_unresolved"} for item in
                ("NRS 484B.287", "484B.290", "484B.350")],
            "timing": {"description": "Compare observed complete crossing frame strictly with first displayed zero frame on synchronized original 20 Hz evidence.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": "introductory exception applicability",
                "note": "Referenced statutory exceptions are retained as original context for independent review."}]}})
    judgment_ref = write("judgment-1.json", {"status": "draft",
        "template_id": TEMPLATE, "phrase": "introductory exception applicability",
        "note": "Referenced statutory exceptions are retained as original context for independent review.",
        "observable_requirements": {"observables": [
            {"name": "signal_countdown", "unit": "indication and integer",
                "description": "Original facing illuminated flashing form and legible countdown at 20 Hz."},
            {"name": "pedestrian_crossing", "unit": "position",
                "description": "Original entry and complete highway crossing frames."}],
            "context_inputs": [{"name": "reviewed_countdown_site", "unit": "source",
                "description": "Source-hashed one-way public highway, crossing and governing signal."}],
            "recording_needs": [{"name": channel["name"], "unit": channel["unit"],
                "description": channel["method"]} for channel in recording_description()["channels"]],
            "sweep_dimensions": [], "landmarks": [],
            "limitations": ["Introductory exceptions require independent review."]}})
    bindings_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}],
        context_refs=[],
        established_contexts=["Frozen C150911 one-way-road/crosswalk cell identity; original Native site qualification pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": "C150911",
            "rationale": "Frozen catalog identity, not physical proof."}],
        variable_parameters=[{"name": name, "kind": "world_setup",
            "range_or_domain": domain, "used_by_laws": [LAW]} for name, domain in variables]))
    cases = [{"case_id": HERE.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Neutral source-gated signal and crossing reference; not selected for recording.",
        "variable_assignments": {name: {"kind": "world_setup", "value": value}
            for name, value in (("signal_form", "dont_walk"),
                ("direction", "forward"), ("completion", "before_zero"))},
        "recording_description": recording_description(),
        "unresolved_judgment_calls": ["introductory exception applicability"]}]
    for case in plan["cases"]:
        values = {name: case[name] for name in ("signal_form", "direction", "completion")}
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "boundary_probe" if case["signal_form"] == "dont_walk" else "judgment_sweep",
            "rationale": "Controlled original signal, countdown, direction and complete highway crossing observations.",
            "variable_assignments": {name: {"kind": "world_setup", "value": value}
                for name, value in values.items()},
            "paired_probe_id": "flashing-countdown-completion",
            "deliberate_differences": list(values),
            "unresolved_judgment_calls": ["introductory exception applicability"],
            "recording_description": recording_description(),
            "probe": {"primary_variable": "completion",
                "comparison_or_standard": "first displayed zero on original 20 Hz frame map",
                "target_value_or_branch": values}})
    sweep = {"sweep_id": "source-gated-exception-context", "target_law_id": LAW,
        "judgment_refs": [{"phrase": "introductory exception applicability",
            "note": "Referenced statutory exceptions are retained as original context for independent review."}],
        "status": "incomplete",
        "rationale": "Referenced exceptions require independent original source and legal review; no numeric legal cutoff is invented.",
        "missing_inputs": ["reviewed original exception applicability under NRS 484B.287, .290 and .350",
            "source-bound official pedestrian display and one-way crossing geometry"]}
    write("pending-source-exception-sweep.json", sweep)
    cases_ref = write("cases.json", dict(common, cases=cases,
        sweep_specs=[sweep], sweeps_expanded=True,
        sweep_expansion_scope="Six source-gated crossing probes; statutory zero equality and signal alternatives are explicit."))
    index = {"format": "worker-semantic-delivery", "assignment_id": HERE.name,
        "stages": {"relevance_batch": batch_ref, "relevance": relevance_ref,
            "template": template_ref, "judgment_observables": [judgment_ref],
            "bindings": bindings_ref, "cases": cases_ref}}
    write("semantic-index.json", index)
    return index


if __name__ == "__main__":
    build()
    print("six exact 1d2 semantic proposals authored")
