"""Construct matched police-blueprint ordinary/authorized exception probes.

The fixture packet is synthetic diagnostic input. Local capture must stage two
independently reviewable packets before running the authorized job.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
SOURCE = json.loads((HERE / "construction.json").read_text())
DIAGNOSTIC = json.loads((HERE / "diagnostic-input.json").read_text())
CONTRACT = json.loads((HERE / "first-measurement-contract.json").read_text())
MANIFEST = HERE / "execution-manifest.json"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = path.name == "diagnostic.json"
    path.write_text(json.dumps(data, separators=(",", ":") if compact else None,
                               indent=None if compact else 2) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_one(value, before, after):
    if value.count(before) != 1:
        raise ValueError("Expected one source construction point: " + before)
    return value.replace(before, after)


def build_construction(suffix, authorized):
    case = BASE + "__" + suffix
    data = deepcopy(SOURCE)
    data["case_id"] = case
    files = {row["path"]: row for row in data["files"]}
    runner = files["runner.py"]["content"]
    runner = runner.replace("__traveling_follow_500ft", "__" + suffix)
    runner = replace_one(runner, 'from follow_controller import control_step',
                         'from follow_controller import control_step\nfrom exception_capture import retain_exception_source')
    runner = replace_one(runner, '"vehicle.tesla.model3"', '"vehicle.dodge.charger_police"')
    runner = replace_one(runner, 'owned.append(ego)\n        for name in CAMERAS:',
                         'owned.append(ego)\n        retain_exception_source(output, ego.id, config["fire_context"])\n        for name in CAMERAS:')
    files["runner.py"]["content"] = runner
    files["exception_capture.py"] = {"path": "exception_capture.py",
                                      "content": (HERE / "exception_capture.py").read_text()}
    files["exception_source.py"]["content"] = (
        HERE / "exception_source_packet_bound.py").read_text()
    config = json.loads(files["config.json"]["content"])
    config["selected_case_id"] = case
    config["supported_case_ids"] = [case]
    config["case"]["case_id"] = case
    config["fire_context"]["subject_authorized_emergency"] = authorized
    config["fire_context"]["subject_official_business"] = authorized
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    test = files["tests/test_runner.py"]["content"]
    test = test.replace("__traveling_follow_500ft", "__" + suffix)
    files["tests/test_runner.py"]["content"] = test
    data["files"] = list(files.values())
    data["mechanisms"] = list(data["mechanisms"]) + [
        "Matched police blueprint with separate retained emergency authorization and duty packets"]
    return data


def build_diagnostic(suffix, authorized, folder):
    case = BASE + "__" + suffix
    data = deepcopy(DIAGNOSTIC)
    context = json.loads(data["files"]["fire_context.json"])
    context["subject_authorized_emergency"] = authorized
    context["subject_official_business"] = authorized
    data["files"]["fire_context.json"] = json.dumps(context, indent=2) + "\n"
    for name in ("capture/manifest.json", "fixture-provenance.json"):
        value = json.loads(data["files"][name])
        value["case_id"] = case
        data["files"][name] = json.dumps(value, indent=2) + "\n"
    if authorized:
        source = {"ego_id": "ego"}
        for premise, filename in (("authorized_emergency", "authorization.json"),
                                  ("official_business", "official_business.json")):
            path = "source_packets/" + filename
            packet = {"ego_id": "ego", "asserted": True,
                      "source_ref": "synthetic diagnostic dispatch/" + premise}
            data["files"][path] = json.dumps(packet, indent=2) + "\n"
            source[premise] = {"asserted": True, "source_ref": packet["source_ref"],
                               "packet": path,
                               "packet_sha256": sha256(data["files"][path].encode()).hexdigest()}
        data["files"]["subject_exception_source.json"] = json.dumps(source, indent=2) + "\n"
    save(folder / "diagnostic.json", data)
    relative = (folder / "diagnostic.json").relative_to(ROOT).as_posix()
    save(folder / "diagnostic-recipe.json", {
        "format": "worker-fixture-recipe",
        "sources": [{"path": "diagnostic.json", "source": relative,
                     "sha256": digest(folder / "diagnostic.json")}],
        "generator": {"source": relative, "sha256": digest(folder / "diagnostic.json")}})


def main():
    manifest = json.loads(MANIFEST.read_text())
    reference = manifest["cases"][0]
    for suffix, authorized in (("ordinary_police_at500", False),
                               ("authorized_police_at500", True)):
        case = BASE + "__" + suffix
        folder = HERE / "cases" / suffix
        construction = build_construction(suffix, authorized)
        save(folder / "construction.json", construction)
        build_diagnostic(suffix, authorized, folder)
        contract = deepcopy(CONTRACT)
        contract["case_id"] = case
        contract["requirements"][0]["disposition_index"] = 3
        contract["requirements"][0]["requirement"] = (
            "authorized emergency vehicle on official business exception")
        if authorized:
            contract["requirements"][0]["inputs"] += ["subject_exception_source.json"]
        save(folder / "measurement-contract.json", contract)
        entry = {
            "case_id": case, "kind": "delivery",
            "construction": (folder / "construction.json").relative_to(HERE).as_posix(),
            "construction_sha256": digest(folder / "construction.json"),
            "measurement_contract": (folder / "measurement-contract.json").relative_to(HERE).as_posix(),
            "measurement_procedure": deepcopy(reference["measurement_procedure"]),
            "fixture_recipe": (folder / "diagnostic-recipe.json").relative_to(ROOT).as_posix(),
            "native_handoff": deepcopy(reference["native_handoff"]),
            "acquisition": deepcopy(reference["acquisition"]),
            "candidate_risk": {"status": "physical", "reason":
                "Police-blueprint subject may not sustain the measured following gap or be visible in all original views"},
            "candidates": [],
        }
        manifest["cases"] = [row for row in manifest["cases"] if row["case_id"] != case] + [entry]
    save(MANIFEST, manifest)
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    ids = [BASE + "__ordinary_police_at500", BASE + "__authorized_police_at500"]
    plan["cases"] = [row for row in plan["cases"] if row["case_id"] not in ids]
    for suffix, authorized in (("ordinary_police_at500", False),
                               ("authorized_police_at500", True)):
        plan["cases"].append({
            "case_id": BASE + "__" + suffix, "target_law_id": "NRS-484B-710",
            "branch": "traveling_follow", "target_distance_ft": 500,
            "gap_ids": ["authorized-exception"],
            "construction_status": "exact_bundle_pending_proofs",
            "physical_risk": {
                "risk": "Police-blueprint subject may not sustain the following gap or be visible",
                "trigger_source": "original footprint/state and four original RGB streams",
                "trigger_metric": "active measured gap and participant pixel visibility",
                "failure_condition": "Missing measured active frames or missing subject pixels"},
            "exception_premise": "sourced authorization and official business" if authorized else "ordinary subject"
        })
    disposition = plan["requirement_dispositions"][3]
    disposition["status"] = "selected_required"
    disposition["case_ids"] = ids
    disposition["evidence_or_gap"] = "Matched police-blueprint exception pair with separate retained source packets; exact proofs pending."
    plan["comparisons"] = [row for row in plan["comparisons"] if row["comparison_id"] != "authorized_emergency_exception"]
    plan["comparisons"].append({
        "comparison_id": "authorized_emergency_exception", "case_ids": ids,
        "fixed_conditions": ["same police blueprint and C109514 through-intersection route",
                             "same 500 ft commanded gap and measured original footprints",
                             "same fire apparatus alarm response, cameras, duration and controller"],
        "deliberate_differences": ["separately sourced subject emergency authorization and official-business duty"]})
    save(path, plan)
    path = HERE / "proposals/cases.json"
    proposals = json.loads(path.read_text())
    reference_proposal = next(row for row in proposals["cases"] if row["case_id"].endswith("__traveling_follow_500ft"))
    proposals["cases"] = [row for row in proposals["cases"] if row["case_id"] not in ids]
    for suffix, authorized in (("ordinary_police_at500", False),
                               ("authorized_police_at500", True)):
        row = deepcopy(reference_proposal)
        row["case_id"] = BASE + "__" + suffix
        row["target_type"] = "exception_probe"
        row["rationale"] = "Matched police-blueprint comparison of separately sourced emergency authorization and duty premises"
        row["variable_assignments"]["authorized_on_official_business"] = {
            "kind": "sourced_context", "value": authorized}
        row["paired_probe_id"] = "authorized_emergency_exception"
        row["deliberate_differences"] = ["authorized_on_official_business"]
        row.pop("probe", None)
        proposals["cases"].append(row)
    save(path, proposals)


if __name__ == "__main__":
    main()
