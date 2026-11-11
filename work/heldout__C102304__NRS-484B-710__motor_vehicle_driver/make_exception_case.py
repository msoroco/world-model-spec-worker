"""Build the exact authorized-emergency comparison construction."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__authorized_emergency_at500"
BASE = HERE.name + "__traveling_follow_500ft"
FOLDER = HERE / "cases/authorized_emergency_at500"


def put(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=None if compact else 2,
                               separators=(",", ":") if compact else None) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def bundle(original):
    construction = deepcopy(original)
    construction["case_id"] = CASE
    for item in construction["files"]:
        if item["path"] == "config.json":
            config = json.loads(item["content"])
            config["selected_case_id"] = CASE
            config["case"]["case_id"] = CASE
            config["fire_context"]["subject_authorized_emergency"] = True
            config["fire_context"]["subject_official_business"] = True
            config["fire_context"]["alarm_response_source"] = (
                "authored dispatch and official-business scenario premise; verify against retained local Native scene record")
            item["content"] = json.dumps(config, indent=2) + "\n"
        elif item["path"] == "runner.py":
            if item["content"].count('CASE_SUFFIX = "__traveling_follow_500ft"') != 1:
                raise ValueError("Traveling case binding changed")
            item["content"] = item["content"].replace(
                'CASE_SUFFIX = "__traveling_follow_500ft"',
                'CASE_SUFFIX = "__authorized_emergency_at500"')
            before = '_spawn(world, "vehicle.tesla.model3", route["ego"].transform)'
            after = '_spawn(world, "vehicle.carlamotors.firetruck", route["ego"].transform)'
            if item["content"].count(before) != 1:
                raise ValueError("Traveling subject spawn source changed")
            item["content"] = item["content"].replace(before, after)
            item["content"] = item["content"].replace(
                '    if not isinstance(config.get("case", {}).get("recording_description"), dict):',
                '    if context["subject_authorized_emergency"] is not True or context["subject_official_business"] is not True:\n'
                '        raise ValueError("Exception subject requires separately sourced authorization and official business")\n'
                '    if not isinstance(config.get("case", {}).get("recording_description"), dict):')
        elif item["path"] == "tests/test_runner.py":
            item["content"] = item["content"].replace(BASE, CASE)
            item["content"] = item["content"].replace(
                '"subject_authorized_emergency": False,',
                '"subject_authorized_emergency": True,').replace(
                '"subject_official_business": False}',
                '"subject_official_business": True}')
        elif item["path"] == "tests/test_fire_finalizer.py":
            item["content"] = item["content"].replace(
                'runtime = Path(__file__).resolve().parents[3] / "runtime"',
                'runtime = next(parent / "runtime" for parent in Path(__file__).resolve().parents '
                'if (parent / "runtime/scenario_pipeline").is_dir())')
    return construction


def main():
    FOLDER.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    base = next(item for item in manifest["cases"] if item["case_id"] == BASE)
    construction_path = FOLDER / "construction.json"
    put(construction_path, bundle(json.loads((HERE / base["construction"]).read_text())))
    config = json.loads(next(item["content"] for item in json.loads(construction_path.read_text())["files"]
                             if item["path"] == "config.json"))
    diagnostic = json.loads((HERE / "diagnostic-input.json").read_text())
    diagnostic["files"]["fire_context.json"] = json.dumps(config["fire_context"], indent=2) + "\n"
    if "capture/manifest.json" in diagnostic["files"]:
        capture = json.loads(diagnostic["files"]["capture/manifest.json"])
        capture["case_id"] = CASE
        diagnostic["files"]["capture/manifest.json"] = json.dumps(capture, indent=2) + "\n"
    if "fixture-provenance.json" in diagnostic["files"]:
        provenance = json.loads(diagnostic["files"]["fixture-provenance.json"])
        provenance["case_id"] = CASE
        provenance["scope"] = "Synthetic authorized-emergency software diagnostic; not physical evidence"
        diagnostic["files"]["fixture-provenance.json"] = json.dumps(provenance, indent=2) + "\n"
    diagnostic_path = FOLDER / "diagnostic.json"
    put(diagnostic_path, diagnostic, compact=True)
    relative = diagnostic_path.relative_to(ROOT).as_posix()
    recipe_path = FOLDER / "diagnostic-recipe.json"
    put(recipe_path, {"format": "worker-fixture-recipe",
                      "sources": [{"path": "diagnostic-input.json", "source": relative,
                                   "sha256": digest(diagnostic_path)}],
                      "generator": {"source": relative, "sha256": digest(diagnostic_path)}})
    plan = json.loads((HERE / "case-plan.json").read_text())
    requirement = "authorized emergency vehicle on official business exception to the following-distance restriction"
    source = "NRS 484B.710 full text in inputs/" + HERE.name + "/assignment.json"
    dispositions = plan["requirement_dispositions"]
    match = next((item for item in dispositions if item["requirement"] == requirement), None)
    if match is None:
        dispositions.append({"requirement": requirement, "source": source,
                             "status": "selected_required", "case_ids": [CASE],
                             "evidence_or_gap": "Accepted ordinary-subject summaries do not establish authorization or official business."})
        match = dispositions[-1]
    contract = deepcopy(json.loads((HERE / base["measurement_contract"]).read_text()))
    contract["case_id"] = CASE
    contract["requirements"][0].update(disposition_index=dispositions.index(match),
                                       requirement=requirement, source=source)
    contract_path = FOLDER / "measurement-contract.json"
    put(contract_path, contract)
    entry = {"case_id": CASE, "kind": "delivery",
             "construction": construction_path.relative_to(HERE).as_posix(),
             "construction_sha256": digest(construction_path),
             "measurement_contract": contract_path.relative_to(HERE).as_posix(),
             "measurement_procedure": deepcopy(base["measurement_procedure"]),
             "fixture_recipe": recipe_path.relative_to(ROOT).as_posix(),
             "native_handoff": deepcopy(base["native_handoff"]),
             "candidate_risk": {"status": "physical", "reason": "Emergency subject body geometry and official-business premise may fail the matched-distance comparison"},
             "acquisition": deepcopy(base["acquisition"]), "candidates": []}
    for original in base["candidates"]:
        ident = original["id"]
        path = FOLDER / (ident + "-construction.json")
        put(path, bundle(json.loads((HERE / original["construction"]).read_text())))
        entry["candidates"].append({"id": ident, "construction": path.relative_to(HERE).as_posix(),
                                    "construction_sha256": digest(path),
                                    "trigger": deepcopy(original["trigger"]),
                                    "changed_knobs": deepcopy(original["changed_knobs"])})
    proposal_doc = json.loads((HERE / "proposals/cases.json").read_text())
    proposal = deepcopy(next(item for item in proposal_doc["cases"] if item["case_id"] == BASE))
    proposal.update(case_id=CASE, target_type="exception_probe", rationale=requirement,
                    paired_probe_id="authorized_emergency_500_comparison")
    proposal["variable_assignments"].update(
        subject_authorized_emergency={"kind": "scenario_premise", "value": True},
        subject_official_business={"kind": "scenario_premise", "value": True})
    proposal_doc["cases"] = [item for item in proposal_doc["cases"] if item["case_id"] != CASE] + [proposal]
    put(HERE / "proposals/cases.json", proposal_doc)
    next(item for item in plan["cases"] if item["case_id"] == CASE)["construction_status"] = "exact_bundle_pending_proofs"
    put(HERE / "case-plan.json", plan)
    manifest["cases"] = [item for item in manifest["cases"] if item["case_id"] != CASE] + [entry]
    put(manifest_path, manifest)


if __name__ == "__main__":
    main()
