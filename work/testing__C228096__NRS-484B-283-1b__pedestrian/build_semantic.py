"""Build source-pending canonical semantic proposals for the exact law and cell."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SOURCE = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
LAW_ID = SOURCE["law_id"]
TEMPLATE_ID = LAW_ID + "@pedestrian"
OUT = ROOT / "proposals"


def write(name: str, value: dict) -> None:
    (OUT / (name + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    relevance = {"actor": "pedestrian", "cell_id": "C228096", "status": "draft",
                 "borderline_excluded": [], "relevant_laws": [{"law_id": LAW_ID,
                 "quote": SOURCE["law"]["text"], "confidence": "high",
                 "applies_to": ["pedestrian"]}]}
    write("relevance", relevance)
    write("relevance-batch", relevance)
    params = [{"kind": "world_setup", "name": name, "unit": "categorical",
               "range_or_domain": domain} for name, domain in (
                   ("action", "walk or run"),
                   ("vehicle_gap", "close or far engineering probe; no legal threshold"),
                   ("route_kind", "into vehicle path, roadway only, or remain curb"))]
    judgments = [
        {"phrase": "suddenly leave a curb or other place of safety",
         "note": "Original departure timing, curb and path authority require independent review; gait alone is no legal cutoff."},
        {"phrase": "so close that it is impossible for the driver to yield",
         "note": "Original vehicle motion, driver opportunity and path geometry require independent review; proximity alone is no legal cutoff."},
    ]
    template = {"actor": "pedestrian", "law_id": LAW_ID, "parameter_refs": params,
                "quote": SOURCE["law"]["text"], "status": "draft", "template_id": TEMPLATE_ID,
                "structure": {"activation": {"source_clause": "A pedestrian leaves a curb or other place of safety and walks or runs into the path of a vehicle"},
                              "exceptions": [{"source_clause": SOURCE["law"]["text"].split(": A pedestrian", 1)[0]}],
                              "judgment_calls_needed": judgments,
                              "obligation": {"source_clause": "A pedestrian shall not suddenly leave a curb or other place of safety and walk or run into the path of a vehicle which is so close that it is impossible for the driver to yield"},
                              "timing": {"source_clause": "at departure from the curb or other place of safety"}}}
    write("template", template)
    for i, item in enumerate(judgments):
        topic = "pedestrian and curb geometry" if i == 0 else "vehicle path and driver"
        requirements = {"context_inputs": [{"name": "reviewed curb, roadway and driver authority",
                                            "description": "SHA-256-sealed original site and map", "unit": "source record"}],
                        "landmarks": [], "limitations": ["Original motion and exception context require independent review; engineering probes do not establish the legal judgment."],
                        "observables": [{"name": topic, "description": "20 Hz original Native actor readback and four-camera review", "unit": "source observation"}],
                        "recording_needs": [{"name": topic, "description": "Original saved source and camera review", "unit": "source observation"}],
                        "sweep_dimensions": []}
        write("judgment-" + str(i), {"note": item["note"], "phrase": item["phrase"],
                                    "observable_requirements": requirements, "status": "draft",
                                    "template_id": TEMPLATE_ID})
    write("bindings", {"actor": "pedestrian", "cell_id": "C228096", "context_refs": [],
                       "fixed_parameters": [], "law_refs": [{"binding_kind": "direct", "template_id": TEMPLATE_ID}],
                       "status": "draft", "variable_parameters": [dict(p, used_by_laws=[LAW_ID]) for p in params]})
    stages = {}
    for key, names in {"relevance": ["relevance"], "relevance_batch": ["relevance-batch"],
                       "template": ["template"], "bindings": ["bindings"],
                       "judgment_observables": ["judgment-0", "judgment-1"],
                       "cases": ["cases"]}.items():
        refs = []
        for name in names:
            path = OUT / (name + ".json")
            refs.append({"path": "proposals/" + path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        stages[key] = refs if key == "judgment_observables" else refs[0]
    write("semantic-index", {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
                             "stages": stages})
    print("Built exact C228096 semantic proposals")


if __name__ == "__main__":
    main()
