"""Rebind source-reviewed plan, canonical speed probe and exact constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    ident = "approaching_near_crossing_speed_sweep"
    ids = [case["case_id"] for case in plan["cases"]
           if "__approaching_near_speed_" in case["case_id"]]
    assert len(ids) == 3
    if ident not in {row["comparison_id"] for row in plan["comparisons"]}:
        plan["comparisons"].append({
            "comparison_id": ident,
            "case_ids": ids,
            "fixed_conditions": "Same reviewed non-through intersection, yield device, counterpart, approach phase, requested counterpart station, route, four cameras and 45-second duration; verify original source identity independently.",
            "deliberate_differences": ["requested ego crossing-speed controller target"],
            "interpretation_limit": "Requested speed is an engineering target; original frozen-window body-overlap-to-clearance mean determines training-range coverage, never a legal threshold.",
        })
    plan_sha = write(plan_path, plan)
    proposal_path = HERE / "proposals/cases.json"
    proposal = json.loads(proposal_path.read_text())
    for row in proposal["cases"]:
        suffix = row["case_id"].removeprefix(HERE.name + "__")
        speed = "__approaching_near_speed_" in row["case_id"]
        if speed:
            row["paired_probe_id"] = ident
            row["deliberate_differences"] = ["requested_ego_crossing_speed_mps"]
            row["probe"] = {
                "primary_variable": "requested_ego_crossing_speed_mps",
                "comparison_or_standard": "source-audited original crossing-speed mean against frozen training ranges",
                "target_value_or_branch": row["variable_assignments"]["requested_ego_crossing_speed_mps"]["value"],
            }
        else:
            row["variable_assignments"]["requested_ego_crossing_speed_mps"] = {
                "kind": "controller", "value": "unconstrained",
                "note": "Original station/response construction has no crossing-speed target",
            }
    write(proposal_path, proposal)
    param = {"name": "requested_ego_crossing_speed_mps", "kind": "controller",
             "range_or_domain": "positive requested m/s or unconstrained for original station and response probes"}
    template_path = HERE / "proposals/template.json"
    template = json.loads(template_path.read_text())
    if not any(row["name"] == param["name"] for row in template["parameter_refs"]):
        template["parameter_refs"].append(param)
    write(template_path, template)
    bindings_path = HERE / "proposals/bindings.json"
    bindings = json.loads(bindings_path.read_text())
    if not any(row["name"] == param["name"] for row in bindings["variable_parameters"]):
        bindings["variable_parameters"].append({**param, "used_by_laws": [plan["law_id"]]})
    write(bindings_path, bindings)
    index_path = HERE / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    for name in ("cases", "template", "bindings"):
        ref = index["stages"][name]
        ref["sha256"] = hashlib.sha256((HERE / ref["path"]).read_bytes()).hexdigest()
    write(index_path, index)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        for item in (entry, *entry["candidates"]):
            path = HERE / item["construction"]
            construction = json.loads(path.read_text())
            for file in construction["files"]:
                if file["path"] == "case-plan.json":
                    file["content"] = plan_path.read_text()
                if file["path"] == "config.json":
                    config = json.loads(file["content"])
                    config["plan_sha256"] = plan_sha
                    file["content"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
                    config_path = path.parent / "config.json"
                    if item is entry and config_path.is_file():
                        write(config_path, config)
            item["construction_sha256"] = write(path, construction)
        if entry["case_id"].endswith("__occupied_response"):
            (HERE / "construction.json").write_bytes((HERE / entry["construction"]).read_bytes())
            (HERE / "config.json").write_text(next(f["content"] for f in json.loads((HERE / entry["construction"]).read_text())["files"] if f["path"] == "config.json"))
    write(manifest_path, manifest)
    print("Bound source-reviewed seven-case plan, four comparisons and fourteen constructions")


if __name__ == "__main__":
    main()
