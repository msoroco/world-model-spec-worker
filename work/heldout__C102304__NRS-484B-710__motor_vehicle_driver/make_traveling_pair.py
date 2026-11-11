"""Freeze the 499/501 ft linked probes from the proven 500 ft source pattern."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name + "__traveling_follow_"


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(value, original, replacement):
    if value.count(original) != 1:
        raise ValueError("Expected exactly one selected source edit: " + original)
    return value.replace(original, replacement)


def construction_for(base, target):
    result = deepcopy(base)
    result["case_id"] = PREFIX + str(target) + "ft"
    files = {item["path"]: item for item in result["files"]}
    runner = files["runner.py"]["content"]
    runner = once(runner, 'CASE_SUFFIX = "__traveling_follow_500ft"',
                  'CASE_SUFFIX = "__traveling_follow_' + str(target) + 'ft"')
    runner = once(runner, 'config.get("target_distance_ft") != 500',
                  'config.get("target_distance_ft") != ' + str(target))
    runner = runner.replace('target_gap_ft=500', 'target_gap_ft=' + str(target))
    files["runner.py"]["content"] = runner
    test = files["tests/test_runner.py"]["content"]
    test = test.replace("__traveling_follow_500ft", "__traveling_follow_" + str(target) + "ft")
    test = once(test, '"target_distance_ft": 500',
                '"target_distance_ft": ' + str(target))
    test = once(test, 'config["target_distance_ft"] = 499',
                'config["target_distance_ft"] = ' + str(target + 2))
    files["tests/test_runner.py"]["content"] = test
    config = json.loads(files["config.json"]["content"])
    config["selected_case_id"] = result["case_id"]
    config["target_distance_ft"] = target
    config["case"]["case_id"] = result["case_id"]
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    return result


def diagnostic_for(base, target, destination):
    spec = deepcopy(base)
    files = spec["files"]
    rows = [json.loads(line) for line in files["participant_footprints.jsonl"].splitlines()]
    shift_m = (target - 500) / 3.280839895013123
    for row in rows:
        for corner in row["apparatus_corners"]:
            corner[0] += shift_m
    files["participant_footprints.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    manifest = json.loads(files["capture/manifest.json"])
    manifest["case_id"] = PREFIX + str(target) + "ft"
    files["capture/manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    provenance = json.loads(files["fixture-provenance.json"])
    provenance["case_id"] = manifest["case_id"]
    files["fixture-provenance.json"] = json.dumps(provenance, indent=2) + "\n"
    destination.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    relative = destination.relative_to(ROOT).as_posix()
    return {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": relative,
                         "sha256": digest(destination)}],
            "generator": {"source": relative, "sha256": digest(destination)}}


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    existing = {item["case_id"]: item for item in manifest["cases"]}
    first = existing[PREFIX + "500ft"]
    primary = json.loads((HERE / first["construction"]).read_text())
    fallbacks = {item["id"]: json.loads((HERE / item["construction"]).read_text())
                 for item in first["candidates"]}
    base_diagnostic = json.loads((HERE / "diagnostic-input.json").read_text())
    base_contract = json.loads((HERE / "first-measurement-contract.json").read_text())
    proposal_path = HERE / "proposals/cases.json"
    proposal = json.loads(proposal_path.read_text())
    proposal_cases = {item["case_id"]: item for item in proposal["cases"]}
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for target in (499, 500, 501):
        case_id = PREFIX + str(target) + "ft"
        case = proposal_cases.get(case_id, deepcopy(proposal_cases[PREFIX + "500ft"]))
        case["case_id"] = case_id
        case["rationale"] = "Measure traveling-apparatus full-body gap at the " + str(target) + " ft engineering command against the statutory 500 ft boundary"
        case["variable_assignments"]["target_distance_ft"]["value"] = target
        case["paired_probe_id"] = "traveling_500_boundary"
        case["epsilon_used"] = 1
        case["probe"] = {"threshold_ref": "NRS 484B.710 traveling-follow distance",
                         "operator": "<", "unit": "ft", "test_value": target}
        proposal_cases[case_id] = case
    proposal["cases"] = [proposal_cases[key] for key in (PREFIX + "499ft", PREFIX + "500ft", PREFIX + "501ft")]
    put(proposal_path, proposal)
    plan["requirement_dispositions"][0]["case_ids"] = [PREFIX + str(n) + "ft" for n in (499, 500, 501)]
    entries = [first]
    for target in (499, 501):
        case_id = PREFIX + str(target) + "ft"
        folder = HERE / "cases" / ("traveling_follow_" + str(target) + "ft")
        folder.mkdir(parents=True, exist_ok=True)
        primary_path = folder / "construction.json"
        put(primary_path, construction_for(primary, target))
        diagnostic_path = folder / "diagnostic.json"
        recipe_path = folder / "diagnostic-recipe.json"
        put(recipe_path, diagnostic_for(base_diagnostic, target, diagnostic_path))
        contract = deepcopy(base_contract)
        contract["case_id"] = case_id
        put(folder / "measurement-contract.json", contract)
        entry = {
            "case_id": case_id, "kind": "delivery",
            "construction": primary_path.relative_to(HERE).as_posix(),
            "construction_sha256": digest(primary_path),
            "measurement_contract": (folder / "measurement-contract.json").relative_to(HERE).as_posix(),
            "measurement_procedure": {"entrypoint": "fire_finalizer.py"},
            "fixture_recipe": recipe_path.relative_to(ROOT).as_posix(),
            "native_handoff": deepcopy(first["native_handoff"]),
            "candidate_risk": deepcopy(first["candidate_risk"]),
            "acquisition": deepcopy(first["acquisition"]),
            "candidates": [],
        }
        old = existing.get(case_id)
        if old and old.get("construction_sha256") == entry["construction_sha256"]:
            for key in ("offline", "compatibility", "negative", "post_capture"):
                if key in old:
                    entry[key] = old[key]
        old_candidates = {item["id"]: item for item in old.get("candidates", [])} if old else {}
        for ident in ("fallback1", "fallback2", "fallback3"):
            candidate_path = folder / (ident + "-construction.json")
            put(candidate_path, construction_for(fallbacks[ident], target))
            source = next(item for item in first["candidates"] if item["id"] == ident)
            candidate = {"id": ident,
                         "construction": candidate_path.relative_to(HERE).as_posix(),
                         "construction_sha256": digest(candidate_path),
                         "trigger": deepcopy(source["trigger"]),
                         "changed_knobs": deepcopy(source["changed_knobs"])}
            prior = old_candidates.get(ident)
            if prior and prior.get("construction_sha256") == candidate["construction_sha256"]:
                for key in ("offline", "compatibility"):
                    if key in prior:
                        candidate[key] = prior[key]
            entry["candidates"].append(candidate)
        entries.append(entry)
        next(item for item in plan["cases"] if item["case_id"] == case_id)["construction_status"] = "exact_bundle_pending_proofs"
    next(item for item in plan["cases"] if item["case_id"] == PREFIX + "500ft")["construction_status"] = "exact_bundle_software_proved"
    put(plan_path, plan)
    manifest["cases"] = entries + [item for item in manifest["cases"]
                                    if item["case_id"] not in {entry["case_id"] for entry in entries}]
    put(manifest_path, manifest)


if __name__ == "__main__":
    main()
