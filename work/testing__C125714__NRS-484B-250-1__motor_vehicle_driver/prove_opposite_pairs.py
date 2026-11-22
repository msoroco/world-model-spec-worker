"""Source-bound synthetic comparisons of opposing diagnostic cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_audit import audit_comparison


ROOT = Path(__file__).resolve().parent
VARIANTS = ("opposite_straight", "opposite_intends_left", "opposite_makes_left")
ORIGINALS = ("intersection-context.json", "ego-body-history.jsonl",
             "other-body-history.jsonl")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_case(proof_root, suffix):
    folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    fixture = proof_root / suffix / "fixture"
    recipe_path = folder / "diagnostic-recipe.json"
    recipe = json.loads(recipe_path.read_text())
    generator = recipe["generator"]
    spec_path = ROOT.parents[1] / generator["source"]
    spec_bytes = spec_path.read_bytes()
    if sha(spec_bytes) != generator["sha256"]:
        raise ValueError("diagnostic recipe source changed")
    spec = json.loads(spec_bytes)
    acquisition = json.loads((fixture / "acquisition.json").read_text())
    for name in ORIGINALS:
        actual = (fixture / name).read_bytes()
        if (actual.decode() != spec["files"][name] or
                acquisition[name]["sha256"] != sha(actual)):
            raise ValueError("original diagnostic source changed: " + name)
    map_bytes = (fixture / "road.xodr").read_bytes()
    if sha(map_bytes) != recipe["sources"][0]["sha256"]:
        raise ValueError("diagnostic map source changed")
    context = json.loads((fixture / "intersection-context.json").read_text())
    trace = {"context": context["law_context"], "crossing": context["crossing"]}
    for party in ("ego", "other"):
        trace[party + "_samples"] = [json.loads(line) for line in
            (fixture / (party + "-body-history.jsonl")).read_text().splitlines()]
    return trace, {name: sha((fixture / name).read_bytes()) for name in ORIGINALS}


def prove(proof_root):
    traces = [load_case(proof_root, suffix) for suffix in VARIANTS]
    comparison = audit_comparison(traces[0][0], traces[1][0], ["left_turn_intent"])
    left, right = comparison["left"], comparison["right"]
    if (left["opposite_left_exclusion"] is not False or
            right["opposite_left_exclusion"] is not True or
            left["legal_judgment"] != "unresolved" or
            right["legal_judgment"] != "unresolved"):
        raise ValueError("opposite intention did not isolate diagnostic exclusion")
    try:
        audit_comparison(traces[0][0], traces[1][0], ["devices"])
    except ValueError as error:
        if "undeclared difference: left_turn_intent" not in str(error):
            raise
    else:
        raise ValueError("undeclared intention change was accepted")
    realization = audit_comparison(traces[1][0], traces[2][0], ["left_turn_realized"])
    if (realization["left"]["observed_left_turn"] is not False or
            realization["right"]["observed_left_turn"] is not True or
            realization["right"]["opposite_left_exclusion"] is not True or
            realization["right"]["legal_judgment"] != "unresolved"):
        raise ValueError("actual left-turn body motion was not isolated")
    try:
        audit_comparison(traces[1][0], traces[2][0], ["devices"])
    except ValueError as error:
        if "undeclared difference: left_turn_realized" not in str(error):
            raise
    else:
        raise ValueError("undeclared actual turn was accepted")
    receipt = {
        "format": "c125714-opposite-diagnostic-pairs",
        "diagnostic_only": True,
        "case_ids": [ROOT.name + "__" + suffix for suffix in VARIANTS],
        "fixture_source_sha256": [item[1] for item in traces],
        "declared_differences": ["left_turn_intent", "left_turn_realized"],
        "observed_left_turn": [False, False, True],
        "negative_undeclared_differences_rejected": True,
        "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
    }
    (ROOT / "opposite-pairs-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"cases": receipt["case_ids"], "diagnostic": True,
                      "declared_differences": receipt["declared_differences"],
                      "negative": "rejected"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", type=Path, required=True)
    prove(parser.parse_args().proof_root)
