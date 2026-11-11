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
CASES = (("ordinary_police_at499", False, False),
         ("authorized_offduty_at499", True, False),
         ("unauthorized_onduty_at499", False, True),
         ("authorized_police_at499", True, True))


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


def build_construction(suffix, authorized, official_business):
    case = BASE + "__" + suffix
    data = deepcopy(SOURCE)
    data["case_id"] = case
    files = {row["path"]: row for row in data["files"]}
    runner = files["runner.py"]["content"]
    runner = runner.replace("__traveling_follow_500ft", "__" + suffix)
    runner = runner.replace("target_gap_ft=500", "target_gap_ft=499")
    runner = runner.replace('target_distance_ft") != 500', 'target_distance_ft") != 499')
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
    files.pop("tests/test_fire_finalizer.py")
    files["tests/test_exception_capture.py"] = {
        "path": "tests/test_exception_capture.py",
        "content": (HERE / "tests/test_exception_capture.py").read_text()}
    config = json.loads(files["config.json"]["content"])
    config["selected_case_id"] = case
    config["supported_case_ids"] = [case]
    config["case"]["case_id"] = case
    config["target_distance_ft"] = 499
    config["fire_context"]["subject_authorized_emergency"] = authorized
    config["fire_context"]["subject_official_business"] = official_business
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    test = files["tests/test_runner.py"]["content"]
    test = test.replace("__traveling_follow_500ft", "__" + suffix)
    test = test.replace('"target_distance_ft": 500', '"target_distance_ft": 499')
    test = test.replace('config["target_distance_ft"] = 499',
                        'config["target_distance_ft"] = 500')
    files["tests/test_runner.py"]["content"] = test
    data["files"] = list(files.values())
    data["mechanisms"] = list(data["mechanisms"]) + [
        "Matched police blueprint with separate retained emergency authorization and duty packets"]
    return data


def build_diagnostic(suffix, authorized, official_business, folder):
    case = BASE + "__" + suffix
    data = deepcopy(DIAGNOSTIC)
    footprints = [json.loads(line) for line in data["files"]["participant_footprints.jsonl"].splitlines()]
    for row in footprints:
        for corner in row["apparatus_corners"]:
            corner[0] -= 1 / 3.280839895013123
    data["files"]["participant_footprints.jsonl"] = "".join(
        json.dumps(row, separators=(",", ":")) + "\n" for row in footprints)
    context = json.loads(data["files"]["fire_context.json"])
    context["subject_authorized_emergency"] = authorized
    context["subject_official_business"] = official_business
    data["files"]["fire_context.json"] = json.dumps(context, indent=2) + "\n"
    for name in ("capture/manifest.json", "fixture-provenance.json"):
        value = json.loads(data["files"][name])
        value["case_id"] = case
        data["files"][name] = json.dumps(value, indent=2) + "\n"
    if authorized or official_business:
        source = {"ego_id": "ego"}
        for premise, filename in (("authorized_emergency", "authorization.json"),
                                  ("official_business", "official_business.json")):
            path = "source_packets/" + filename
            asserted = authorized if premise == "authorized_emergency" else official_business
            packet = {"ego_id": "ego", "asserted": asserted,
                      "source_ref": "synthetic diagnostic dispatch/" + premise}
            data["files"][path] = json.dumps(packet, indent=2) + "\n"
            source[premise] = {"asserted": asserted, "source_ref": packet["source_ref"],
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
    for suffix, authorized, official_business in CASES:
        case = BASE + "__" + suffix
        folder = HERE / "cases" / suffix
        construction = build_construction(suffix, authorized, official_business)
        save(folder / "construction.json", construction)
        build_diagnostic(suffix, authorized, official_business, folder)
        contract = deepcopy(CONTRACT)
        contract["case_id"] = case
        contract["requirements"][0]["disposition_index"] = 3
        contract["requirements"][0]["requirement"] = (
            "authorized emergency vehicle on official business exception")
        if authorized or official_business:
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
        manifest["cases"] = [row for row in manifest["cases"]
                             if row["case_id"] != case and not row["case_id"].endswith("_police_at500")] + [entry]
    save(MANIFEST, manifest)
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    ids = [BASE + "__" + suffix for suffix, _, _ in CASES]
    plan["cases"] = [row for row in plan["cases"]
                     if row["case_id"] not in ids and not row["case_id"].endswith("_police_at500")]
    for suffix, authorized, official_business in CASES:
        plan["cases"].append({
            "case_id": BASE + "__" + suffix, "target_law_id": "NRS-484B-710",
            "branch": "traveling_follow", "target_distance_ft": 499,
            "gap_ids": ["authorized-exception"],
            "construction_status": "exact_bundle_pending_proofs",
            "physical_risk": {
                "risk": "Police-blueprint subject may not sustain the following gap or be visible",
                "trigger_source": "original footprint/state and four original RGB streams",
                "trigger_metric": "active measured gap and participant pixel visibility",
                "failure_condition": "Missing measured active frames or missing subject pixels"},
            "exception_premise": {"authorized_emergency": authorized,
                                  "official_business": official_business}
        })
    disposition = plan["requirement_dispositions"][3]
    disposition["status"] = "selected_required"
    disposition["case_ids"] = ids
    disposition["evidence_or_gap"] = "Matched police-blueprint four-way conjunction with separate retained source packets; exact proofs pending."
    plan["comparisons"] = [row for row in plan["comparisons"] if row["comparison_id"] != "authorized_emergency_exception"]
    plan["comparisons"].append({
        "comparison_id": "authorized_emergency_exception", "case_ids": ids,
        "fixed_conditions": ["same police blueprint and C109514 through-intersection route",
                             "same 499 ft commanded gap and measured original footprints",
                             "same fire apparatus alarm response, cameras, duration and controller"],
        "deliberate_differences": ["separately sourced subject emergency authorization and official-business duty"]})
    save(path, plan)
    path = HERE / "proposals/cases.json"
    proposals = json.loads(path.read_text())
    reference_proposal = next(row for row in proposals["cases"] if row["case_id"].endswith("__traveling_follow_500ft"))
    proposals["cases"] = [row for row in proposals["cases"]
                          if row["case_id"] not in ids and not row["case_id"].endswith("_police_at500")]
    for suffix, authorized, official_business in CASES:
        row = deepcopy(reference_proposal)
        row["case_id"] = BASE + "__" + suffix
        row["target_type"] = "compliant_attempt" if authorized and official_business else "violating_attempt"
        row["rationale"] = "Matched police-blueprint comparison of separately sourced emergency authorization and duty premises"
        row["variable_assignments"]["target_distance_ft"]["value"] = 499
        row["variable_assignments"]["target_centre_ft"]["value"] = 499
        row["variable_assignments"]["subject_authorized_emergency"]["value"] = authorized
        row["variable_assignments"]["subject_official_business"]["value"] = official_business
        row["paired_probe_id"] = "authorized_emergency_exception"
        row["deliberate_differences"] = ["subject_authorized_emergency", "subject_official_business"]
        row["probe"] = {"primary_variable": "subject_authorized_emergency",
                        "comparison_or_standard": "NRS 484B.710 exception applies only to authorized emergency vehicles on official business",
                        "target_value_or_branch": suffix}
        proposals["cases"].append(row)
    save(path, proposals)


if __name__ == "__main__":
    main()
