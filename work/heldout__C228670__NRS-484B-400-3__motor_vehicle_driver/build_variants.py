"""Construct the two controlled approach/departure variants without changing identity."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from turn_native_plan import ASSIGNMENT, OFFSETS_M
from build_fallbacks import SPECS

ROOT = Path(__file__).resolve().parent
FIRST = ASSIGNMENT + "__centerline_approach_left_curb_departure"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    primary = json.loads((ROOT / "construction.json").read_text())
    manifest_path = ROOT / "provisional-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    first = manifest["cases"][0]
    proposals_path = ROOT / "proposals/cases.json"
    proposals = json.loads(proposals_path.read_text())
    source_proposal = proposals["cases"][0]
    contract = json.loads((ROOT / "measurement-contract.json").read_text())
    for suffix, (approach, departure) in OFFSETS_M.items():
        if suffix == "centerline_approach_left_curb_departure":
            continue
        case = ASSIGNMENT + "__" + suffix
        if any(row["case_id"] == case for row in manifest["cases"]):
            continue
        stem = suffix.replace("_", "-")
        construction = deepcopy(primary)
        construction["case_id"] = case
        config_file = next(row for row in construction["files"] if row["path"] == "config.json")
        config = json.loads(config_file["content"])
        config["selected_case_id"] = case
        config["case"]["case_id"] = case
        config["engineering"]["approach_target_offset_m"] = approach
        config["engineering"]["departure_target_offset_m"] = departure
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        runner = next(row for row in construction["files"] if row["path"] == "runner.py")
        runner["content"] = runner["content"].replace(
            'ASSIGNMENT + "__centerline_approach_left_curb_departure"',
            'ASSIGNMENT + "__' + suffix + '"')
        if runner["content"] == next(row for row in primary["files"] if row["path"] == "runner.py")["content"]:
            raise ValueError("Variant runner identity unchanged")
        name = stem + "-construction.json"
        construction_sha = write(ROOT / name, construction)
        contract_name = stem + "-measurement-contract.json"
        variant_contract = deepcopy(contract)
        variant_contract["case_id"] = case
        write(ROOT / contract_name, variant_contract)
        proposal = deepcopy(source_proposal)
        proposal["case_id"] = case
        proposal["variable_assignments"]["approach_target_offset_m"]["value"] = approach
        proposal["variable_assignments"]["departure_target_offset_m"]["value"] = departure
        proposal["rationale"] = "Controlled source-surveyed lateral target variant; physical position and practicability require original review."
        proposals["cases"].append(proposal)
        entry = {key: deepcopy(first[key]) for key in
                 ("kind", "measurement_procedure", "candidate_risk", "acquisition")}
        entry.update(case_id=case, construction=name,
                     construction_sha256=construction_sha,
                     measurement_contract=contract_name)
        manifest["cases"].append(entry)
    for entry in manifest["cases"][1:]:
        if entry.get("candidates"):
            continue
        stem = entry["case_id"].split("__")[-1].replace("_", "-")
        base = json.loads((ROOT / entry["construction"]).read_text())
        candidates = []
        for ident, knob, value, source, metric, failure in SPECS:
            alternative = deepcopy(base)
            config_file = next(row for row in alternative["files"] if row["path"] == "config.json")
            config = json.loads(config_file["content"])
            config["engineering"][knob] = value
            config_file["content"] = json.dumps(config, indent=2) + "\n"
            name = stem + "-" + ident + "-construction.json"
            candidates.append({"id": ident, "construction": name,
                               "construction_sha256": write(ROOT / name, alternative),
                               "changed_knobs": [f"{knob}={value}"],
                               "trigger": {"source": source, "metric": metric,
                                           "failure_condition": failure}})
        entry["candidates"] = candidates
    original_diagnostic = (ROOT / "diagnostic.json").read_text()
    if original_diagnostic.count(FIRST) != 1:
        raise ValueError("Diagnostic source identity needs review")
    for entry in manifest["cases"][1:]:
        stem = entry["case_id"].split("__")[-1].replace("_", "-")
        diagnostic_name = stem + "-diagnostic.json"
        diagnostic = ROOT / diagnostic_name
        source_fixture = json.loads(original_diagnostic.replace(FIRST, entry["case_id"]))
        suffix = entry["case_id"].split("__")[-1]
        shift_axis = 1 if suffix == "farther_approach_left_curb_departure" else 0
        shift_phases = ("approach", "entry") if shift_axis == 1 else ("departure",)
        shift_m = -1.0 if shift_axis == 1 else 1.0
        rows = [json.loads(line) for line in source_fixture["files"]["body_corners_original.jsonl"].splitlines() if line]
        for row in rows:
            if row["phase"] in shift_phases:
                for corner in row["body_corners_xy_m"]:
                    corner[shift_axis] += shift_m
        source_fixture["files"]["body_corners_original.jsonl"] = "".join(json.dumps(row) + "\n" for row in rows)
        trace = [json.loads(line) for line in source_fixture["files"]["trace.jsonl"].splitlines() if line]
        if len(trace) != len(rows):
            raise ValueError("Diagnostic trace/body join differs")
        axis = "y" if shift_axis == 1 else "x"
        for motion, body in zip(trace, rows):
            if (motion["frame"], motion["time_s"]) != (body["frame"], body["time_s"]):
                raise ValueError("Diagnostic trace/body frame identity differs")
            if body["phase"] in shift_phases:
                motion["position_m"][shift_axis] += shift_m
                motion["position"][axis] += shift_m
        source_fixture["files"]["trace.jsonl"] = "".join(json.dumps(row) + "\n" for row in trace)
        evidence = [json.loads(line) for line in source_fixture["files"]["capture/evidence.jsonl"].splitlines() if line]
        if len(evidence) != len(rows):
            raise ValueError("Diagnostic capture/body join differs")
        for packet, body in zip(evidence, rows):
            if packet["original_frame"] != body["frame"]:
                raise ValueError("Diagnostic capture/body frame differs")
            if body["phase"] in shift_phases:
                ego = packet["ego"]
                ego["position_m"][shift_axis] += shift_m
                for vertex in ego["body_vertices_m"]:
                    vertex[shift_axis] += shift_m
                participant = packet["original_observations"]["participants"][0]
                participant["position_m"][shift_axis] += shift_m
                for vertex in participant["body_vertices_m"]:
                    vertex[shift_axis] += shift_m
        source_fixture["files"]["capture/evidence.jsonl"] = "".join(json.dumps(row) + "\n" for row in evidence)
        by_frame = {packet["original_frame"]: packet["original_observations"] for packet in evidence}
        for graph in source_fixture["graphs"]:
            frame = graph["attributes"].get("frame")
            if frame in by_frame and "observed_evidence" in graph["attributes"]:
                graph["attributes"]["observed_evidence"] = by_frame[frame]
        capture_manifest = json.loads(source_fixture["files"]["capture/manifest.json"])
        capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(
            source_fixture["files"]["trace.jsonl"].encode()).hexdigest()
        source_fixture["files"]["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
        provenance = json.loads(source_fixture["files"]["fixture-provenance.json"])
        provenance["controlled_diagnostic_shift"] = {"axis": "y" if shift_axis == 1 else "x",
                                                       "phases": shift_phases, "meters": shift_m,
                                                       "physical_realization_claimed": False}
        source_fixture["files"]["fixture-provenance.json"] = json.dumps(provenance) + "\n"
        diagnostic.write_text(json.dumps(source_fixture, separators=(",", ":")) + "\n")
        diagnostic_sha = hashlib.sha256(diagnostic.read_bytes()).hexdigest()
        source = "work/" + ROOT.name + "/" + diagnostic_name
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": source,
                               "sha256": diagnostic_sha}],
                  "generator": {"source": source, "sha256": diagnostic_sha}}
        recipe_name = stem + "-recipe.json"
        write(ROOT / recipe_name, recipe)
        entry["fixture_recipe"] = "work/" + ROOT.name + "/" + recipe_name
    write(proposals_path, proposals)
    write(manifest_path, manifest)
    return [row["case_id"] for row in manifest["cases"]]


if __name__ == "__main__":
    print("\n".join(build()))
