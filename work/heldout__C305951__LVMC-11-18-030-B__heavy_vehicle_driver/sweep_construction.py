"""Build exact CPU construction variants for the two heavy-lane judgment grids.

This stages construction inputs only. A staged variant is not a delivered case
until its exact fallback, saved-processing, physical, and comparison proofs pass.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from batch_pipeline.sweeps import grid
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.identity_preflight import validate as validate_identity


SOURCE_CASES = {
    "heavy_passing_plan": "passing_boundary_crossing",
    "heavy_turn_plan": "lawful_turn_preparation_boundary_crossing",
}


def _variant(source: dict, old_case: str, new_case: str, setpoint_m: float) -> dict:
    """Retain the source case's full implementation, changing identity and target."""
    if not isinstance(setpoint_m, (int, float)) or not 0 <= setpoint_m <= 2.2:
        raise ValueError("Sweep setpoint is outside the authored engineering grid")

    def replace(value):
        if isinstance(value, str):
            return value.replace(old_case, new_case)
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    result = replace(deepcopy(source))
    if result["case_id"] != new_case:
        raise ValueError("Source construction identity differs")
    configs = [item for item in result["files"] if item["path"] == "config.json"]
    if len(configs) != 1:
        raise ValueError("Exact construction needs one config.json")
    config = json.loads(configs[0]["content"])
    if config["selected_case_id"] != new_case or config["case"]["case_id"] != new_case:
        raise ValueError("Constructed configuration selected another case")
    if config["supported_case_ids"] != [new_case]:
        raise ValueError("Constructed runner supports another case")
    config["engineering"]["lateral_offset_m"] = float(setpoint_m)
    configs[0]["content"] = json.dumps(config, indent=2) + "\n"
    runners = [item for item in result["files"] if item["path"] == "runner.py"]
    if len(runners) != 1:
        raise ValueError("Exact construction needs one runner.py")
    positive_only = "or not isfinite(value) or value <= 0:"
    nonnegative_lateral = ("or not isfinite(value) or "
                           "(value < 0 if key == 'lateral_offset_m' else value <= 0):")
    if runners[0]["content"].count(positive_only) != 1:
        raise ValueError("Selected runner knob validation changed")
    runners[0]["content"] = runners[0]["content"].replace(
        positive_only, nonnegative_lateral, 1)
    validate_identity(result, result["law_id"], result["cell_id"])
    for item in result["files"]:
        if item["path"].endswith(".py"):
            compile(item["content"], new_case + "/" + item["path"], "exec")
    return result


def build(output: Path) -> list[dict]:
    """Write the 6 x 4 source-derived variants to ignored local staging."""
    output = output.resolve()
    if ROOT / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("Choose a fresh directory under ignored .runtime-work")
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    manifest = json.loads((HERE / "provisional-manifest.json").read_text())
    specs = {spec["sweep_id"]: spec for spec in proposal["sweep_specs"]}
    if set(specs) != set(SOURCE_CASES):
        raise ValueError("Heavy-lane sweep inventory changed")
    planned = []
    for sweep_id, suffix in SOURCE_CASES.items():
        spec = specs[sweep_id]
        if len(spec["axes"]) != 1 or spec["axes"][0]["variable"] != "lateral_control_setpoint_m":
            raise ValueError("Unsupported heavy-lane sweep axis")
        base_case = HERE.name + "__" + suffix
        matches = [case for case in manifest["cases"] if case["case_id"] == base_case]
        if len(matches) != 1:
            raise ValueError("Selected base case is missing")
        base = matches[0]
        candidates = [("primary", base)] + [(candidate["id"], candidate) for candidate in base["candidates"]]
        if [item[0] for item in candidates] != ["primary", "fallback1", "fallback2", "fallback3"]:
            raise ValueError("Expected selected primary and three distinct fallback plans")
        for rank, point in enumerate(grid(spec)):
            case_id = f"{sweep_id}-{rank:04d}"
            target = point["lateral_control_setpoint_m"]
            for candidate_id, candidate in candidates:
                source_path = HERE / candidate["construction"]
                if sha256(source_path.read_bytes()).hexdigest() != candidate["construction_sha256"]:
                    raise ValueError("Selected construction source changed")
                variant = _variant(json.loads(source_path.read_text()), base_case, case_id, target)
                path = Path(sweep_id) / case_id / f"{candidate_id}-construction.json"
                planned.append({"case_id": case_id, "source_case_id": base_case,
                                "candidate_id": candidate_id, "setpoint_m": target,
                                "path": str(path), "source_sha256": candidate["construction_sha256"],
                                "construction": variant})
    output.mkdir(parents=True)
    index = []
    for item in planned:
        destination = output / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(item["construction"], indent=2) + "\n")
        index.append({key: value for key, value in item.items() if key != "construction"}
                     | {"sha256": sha256(destination.read_bytes()).hexdigest()})
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    cases = []
    for case_id in dict.fromkeys(item["case_id"] for item in index):
        selected = [item for item in index if item["case_id"] == case_id]
        primary = selected[0]
        if primary["candidate_id"] != "primary":
            raise ValueError("Sweep primary selection order differs")
        source = next(case for case in manifest["cases"]
                      if case["case_id"] == primary["source_case_id"])
        cases.append({"case_id": case_id, "construction": primary["path"],
                      "construction_sha256": primary["sha256"],
                      "candidate_risk": deepcopy(source["candidate_risk"]),
                      "candidates": [{"id": item["candidate_id"],
                                      "construction": item["path"],
                                      "construction_sha256": item["sha256"],
                                      "trigger": deepcopy(next(candidate["trigger"]
                                          for candidate in source["candidates"]
                                          if candidate["id"] == item["candidate_id"])),
                                      "changed_knobs": deepcopy(next(candidate["changed_knobs"]
                                          for candidate in source["candidates"]
                                          if candidate["id"] == item["candidate_id"]))}
                                     for item in selected[1:]]})
    (output / "offline-manifest.json").write_text(json.dumps({
        "format": "worker-provisional-manifest", "assignment_id": HERE.name,
        "cases": cases,
    }, indent=2) + "\n")
    for case in cases:
        validate_candidates(output, case, "LVMC-11-18-030-B", "C305951",
                            required=False, require_alternate=True, candidate_count=4)
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build(args.output)
    print(json.dumps({"construction_variants": len(rows),
                      "exact_cases": len({row["case_id"] for row in rows}),
                      "output": str(args.output)}, indent=2))
