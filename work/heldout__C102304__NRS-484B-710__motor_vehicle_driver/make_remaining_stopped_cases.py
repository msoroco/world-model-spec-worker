"""Freeze the remaining five linked stopped-apparatus exact constructions."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGETS = [("stopped_drive_to", 500), ("stopped_drive_to", 550),
           ("stopped_park", 450), ("stopped_park", 500), ("stopped_park", 550)]


def put(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=None if compact else 2,
                               separators=(",", ":") if compact else None) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def box(center, half):
    return [[center-half, -1], [center+half, -1],
            [center+half, 1], [center-half, 1]]


def jsonl(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def bundle(base, case_id, branch, target):
    result = deepcopy(base)
    result["case_id"] = case_id
    config_file = next(item for item in result["files"] if item["path"] == "config.json")
    config = json.loads(config_file["content"])
    config.update(selected_case_id=case_id, fire_branch=branch,
                  target_distance_ft=target)
    config["case"]["case_id"] = case_id
    config_file["content"] = json.dumps(config, indent=2) + "\n"
    return result


def diagnostic(base, case_id, branch, target, context):
    spec = deepcopy(base)
    files = spec["files"]
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    if len(trace) != 9 or len(mapping) != 9:
        raise ValueError("Pinned diagnostic scaffold changed")
    ego_centers = [(trace[min(index, 4)]["position"]["x"] + min(index, 4) * .3)
                   if branch == "stopped_park" else row["position"]["x"] + index * .3
                   for index, row in enumerate(trace)]
    apparatus_center = ego_centers[-1] + target / 3.280839895013123
    footprints, states = [], []
    for index, frame in enumerate(mapping):
        stopped_ego = branch == "stopped_park" and index >= 4
        footprints.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                           "ego_id": "ego", "apparatus_id": "apparatus",
                           "ego_corners": box(ego_centers[index], 2),
                           "apparatus_corners": box(apparatus_center, 3)})
        states.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                       "apparatus_moving": False, "ego_moving": not stopped_ego,
                       "ego_following": False, "ego_parked": stopped_ego,
                       "warning_lamp": True, "siren": None})
    files["participant_footprints.jsonl"] = jsonl(footprints)
    files["participant_state.jsonl"] = jsonl(states)
    files["fire_context.json"] = json.dumps(context, indent=2) + "\n"
    capture = json.loads(files["capture/manifest.json"])
    capture["case_id"] = case_id
    files["capture/manifest.json"] = json.dumps(capture, indent=2) + "\n"
    provenance = json.loads(files["fixture-provenance.json"])
    provenance["case_id"] = case_id
    provenance["scope"] = "Synthetic stopped-apparatus software diagnostic; not physical evidence"
    files["fixture-provenance.json"] = json.dumps(provenance, indent=2) + "\n"
    return spec


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    base_case_id = HERE.name + "__stopped_drive_to_450ft"
    base_entry = next(item for item in manifest["cases"] if item["case_id"] == base_case_id)
    primary = json.loads((HERE / base_entry["construction"]).read_text())
    fallbacks = {item["id"]: json.loads((HERE / item["construction"]).read_text())
                 for item in base_entry["candidates"]}
    base_diagnostic = json.loads((HERE / "cases/stopped_drive_to_450ft/diagnostic.json").read_text())
    base_contract = json.loads((HERE / "cases/stopped_drive_to_450ft/measurement-contract.json").read_text())
    base_proposal = json.loads((HERE / "proposals/cases.json").read_text())
    base_plan = json.loads((HERE / "case-plan.json").read_text())
    source_ref = "NRS 484B.710 full text in inputs/" + HERE.name + "/assignment.json"
    drive_ids = [HERE.name + "__stopped_drive_to_" + str(n) + "ft" for n in (450, 500, 550)]
    park_ids = [HERE.name + "__stopped_park_" + str(n) + "ft" for n in (450, 500, 550)]
    drive = next(item for item in base_plan["requirement_dispositions"]
                 if item["requirement"].startswith("driving to a fire apparatus stopped"))
    drive["case_ids"] = drive_ids
    park_requirement = "parking within the 500 ft boundary of fire apparatus stopped in answer to an alarm"
    park_disposition = next((item for item in base_plan["requirement_dispositions"]
                             if item["requirement"] == park_requirement), None)
    if park_disposition is None:
        park_disposition = {"requirement": park_requirement, "source": source_ref,
                            "status": "selected_required", "case_ids": park_ids,
                            "evidence_or_gap": "Accepted traveling-follow originals do not establish parked subject or stationary apparatus."}
        base_plan["requirement_dispositions"].append(park_disposition)
    elif park_disposition["case_ids"] != park_ids:
        raise ValueError("Existing park disposition changed")
    drive_index = base_plan["requirement_dispositions"].index(drive)
    park_index = base_plan["requirement_dispositions"].index(park_disposition)
    proposal_cases = {item["case_id"]: item for item in base_proposal["cases"]}
    old_manifest = {item["case_id"]: item for item in manifest["cases"]}
    new_entries = []
    for branch, target in TARGETS:
        case_id = HERE.name + "__" + branch + "_" + str(target) + "ft"
        folder = HERE / "cases" / (branch + "_" + str(target) + "ft")
        folder.mkdir(parents=True, exist_ok=True)
        primary_path = folder / "construction.json"
        construction = bundle(primary, case_id, branch, target)
        put(primary_path, construction)
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        diagnostic_path = folder / "diagnostic.json"
        put(diagnostic_path, diagnostic(base_diagnostic, case_id, branch, target,
                                        config["fire_context"]), compact=True)
        relative = diagnostic_path.relative_to(ROOT).as_posix()
        recipe_path = folder / "diagnostic-recipe.json"
        put(recipe_path, {"format": "worker-fixture-recipe",
                          "sources": [{"path": "diagnostic-input.json", "source": relative,
                                       "sha256": digest(diagnostic_path)}],
                          "generator": {"source": relative, "sha256": digest(diagnostic_path)}})
        contract = deepcopy(base_contract)
        contract["case_id"] = case_id
        disposition = drive if branch == "stopped_drive_to" else park_disposition
        contract["requirements"][0].update(
            disposition_index=drive_index if branch == "stopped_drive_to" else park_index,
            requirement=disposition["requirement"], source=disposition["source"])
        contract_path = folder / "measurement-contract.json"
        put(contract_path, contract)
        entry = {"case_id": case_id, "kind": "delivery",
                 "construction": primary_path.relative_to(HERE).as_posix(),
                 "construction_sha256": digest(primary_path),
                 "measurement_contract": contract_path.relative_to(HERE).as_posix(),
                 "measurement_procedure": {"entrypoint": "stopped_finalizer.py"},
                 "fixture_recipe": recipe_path.relative_to(ROOT).as_posix(),
                 "native_handoff": deepcopy(base_entry["native_handoff"]),
                 "candidate_risk": {"status": "physical",
                                    "reason": branch + " may not settle at the measured " + str(target) + " ft center target"},
                 "acquisition": deepcopy(base_entry["acquisition"]),
                 "candidates": []}
        old = old_manifest.get(case_id)
        if old and old.get("construction_sha256") == entry["construction_sha256"]:
            for key in ("offline", "compatibility", "negative", "post_capture"):
                if key in old:
                    entry[key] = old[key]
        old_candidates = {item["id"]: item for item in old.get("candidates", [])} if old else {}
        for ident in ("fallback1", "fallback2", "fallback3"):
            path = folder / (ident + "-construction.json")
            put(path, bundle(fallbacks[ident], case_id, branch, target))
            base_fallback = next(item for item in base_entry["candidates"] if item["id"] == ident)
            candidate = {"id": ident, "construction": path.relative_to(HERE).as_posix(),
                         "construction_sha256": digest(path),
                         "trigger": deepcopy(base_fallback["trigger"]),
                         "changed_knobs": deepcopy(base_fallback["changed_knobs"])}
            if ident == "fallback1":
                candidate["trigger"]["metric"] = "count of crest routes supporting an initial approach beyond " + str(target) + " ft"
            elif ident == "fallback2":
                candidate["trigger"]["metric"] = "measured center-distance and active " + branch + " state"
                candidate["trigger"]["failure_condition"] = ("Primary approach overshoots the " + str(target) + " ft engineering target and leaves no stable active frames; no legal tolerance is inferred.")
            prior = old_candidates.get(ident)
            if prior and prior.get("construction_sha256") == candidate["construction_sha256"]:
                for key in ("offline", "compatibility"):
                    if key in prior:
                        candidate[key] = prior[key]
            entry["candidates"].append(candidate)
        new_entries.append(entry)
        proposal = deepcopy(proposal_cases[base_case_id])
        proposal.update(case_id=case_id, paired_probe_id=branch + "_500_boundary",
                        rationale=disposition["requirement"],
                        recording_description=construction["recording_description"])
        proposal["variable_assignments"]["target_centre_ft"]["value"] = target
        proposal["epsilon_used"] = 50
        proposal["probe"] = {"threshold_ref": "NRS 484B.710 stopped-apparatus distance",
                             "operator": "<", "unit": "ft", "test_value": target}
        proposal_cases[case_id] = proposal
        next(item for item in base_plan["cases"] if item["case_id"] == case_id)["construction_status"] = "exact_bundle_pending_proofs"
    first_proposal = proposal_cases[base_case_id]
    first_proposal["epsilon_used"] = 50
    first_proposal["probe"] = {"threshold_ref": "NRS 484B.710 stopped-apparatus distance",
                               "operator": "<", "unit": "ft", "test_value": 450}
    base_proposal["cases"] = list(proposal_cases.values())
    put(HERE / "proposals/cases.json", base_proposal)
    put(HERE / "case-plan.json", base_plan)
    new_ids = {item["case_id"] for item in new_entries}
    manifest["cases"] = [item for item in manifest["cases"] if item["case_id"] not in new_ids] + new_entries
    put(manifest_path, manifest)


if __name__ == "__main__":
    main()
