"""Build source-pending canonical semantic proposals for the exact signal law."""
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
    relevance = {"actor": "pedestrian", "cell_id": "C227824", "status": "draft",
                 "borderline_excluded": [], "relevant_laws": [{"law_id": LAW_ID,
                 "quote": SOURCE["law"]["text"], "confidence": "high",
                 "applies_to": ["pedestrian"]}]}
    write("relevance", relevance)
    write("relevance-batch", relevance)
    params = [{"kind": "world_setup", "name": name, "unit": "categorical",
               "range_or_domain": domain} for name, domain in (
                   ("movement", "enter or wait"),
                   ("other_device_display", "none or WALK display"))]
    judgment = {"phrase": "unless permitted to proceed by another device as provided in NRS 484B.283",
                "note": "WALK display is observed but permission under NRS 484B.283 requires independent source review."}
    template = {"actor": "pedestrian", "law_id": LAW_ID, "parameter_refs": params,
                "quote": SOURCE["law"]["text"], "status": "draft", "template_id": TEMPLATE_ID,
                "structure": {"activation": {"source_clause": "Where the signal is a steady red with a green turn arrow"},
                              "exceptions": [{"source_clause": judgment["phrase"]}],
                              "judgment_calls_needed": [judgment],
                              "obligation": {"source_clause": "Pedestrians facing such a signal shall not enter the highway"},
                              "timing": {"source_clause": "at first pedestrian highway entry while facing the signal"}}}
    write("template", template)
    requirements = {"context_inputs": [{"name": "reviewed highway, signal and device authority",
                                        "description": "SHA-256-sealed original site, map, signal assets and NRS 484B.283 device authority",
                                        "unit": "source record"}],
                    "landmarks": [], "limitations": ["Another device's WALK display does not alone establish permission under NRS 484B.283."],
                    "observables": [{"name": "other device display and facing",
                                     "description": "20 Hz original Native display and pedestrian-facing readback",
                                     "unit": "source observation"}],
                    "recording_needs": [{"name": "other device display and facing",
                                         "description": "Original saved device and camera review",
                                         "unit": "source observation"}],
                    "sweep_dimensions": []}
    write("judgment-0", {"note": judgment["note"], "phrase": judgment["phrase"],
                         "observable_requirements": requirements, "status": "draft",
                         "template_id": TEMPLATE_ID})
    write("bindings", {"actor": "pedestrian", "cell_id": "C227824", "context_refs": [],
                       "fixed_parameters": [], "law_refs": [{"binding_kind": "direct", "template_id": TEMPLATE_ID}],
                       "status": "draft", "variable_parameters": [dict(p, used_by_laws=[LAW_ID]) for p in params]})
    stages = {}
    for key, names in {"relevance": ["relevance"], "relevance_batch": ["relevance-batch"],
                       "template": ["template"], "bindings": ["bindings"],
                       "judgment_observables": ["judgment-0"], "cases": ["cases"]}.items():
        refs = []
        for name in names:
            path = OUT / (name + ".json")
            refs.append({"path": "proposals/" + path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        stages[key] = refs if key == "judgment_observables" else refs[0]
    write("semantic-index", {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
                             "stages": stages})
    print("Built exact C227824 semantic proposals")


if __name__ == "__main__":
    main()
