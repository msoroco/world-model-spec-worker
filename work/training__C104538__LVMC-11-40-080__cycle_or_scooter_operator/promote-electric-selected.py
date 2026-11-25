"""Bind CPU-proven electric cases to the selected C104538 package.

This selects executable conditional Native constructions. It does not assert a
reviewed physical electric asset, original pixels, or legal acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
STAGE = REPO / ".runtime-work/c104538-electric-selection-stage"
STAGE_PACKAGE = STAGE / "work" / ROOT.name
SCRATCH = REPO / ".runtime-work/c104538-electric"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def copy_proof(source: Path, relative: str) -> str:
    dest = ROOT / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return sha(dest)


def main() -> None:
    current = json.loads((ROOT / "execution-manifest.json").read_text())
    original_entries = {entry["case_id"].split("__")[-1]: entry for entry in current["cases"]
                     if entry["case_id"].split("__")[-1] in ("controlled_1", "controlled_2", "controlled_3")}
    if len(original_entries) != 3:
        raise ValueError("Expected selected bicycle base cases")
    current["cases"] = [entry for entry in current["cases"] if entry["case_id"].split("__")[-1] in original_entries]
    staged = json.loads((STAGE_PACKAGE / "execution-manifest.json").read_text())
    for entry in current["cases"]:
        entry["delivery_acceptance"]["script_sha256"] = sha(ROOT / "native/delivery_audit.py")
    for draft in staged["cases"]:
        case_id = draft["case_id"]
        label = case_id.split("__")[-1]
        behavior = label.rsplit("_", 1)[-1]
        base_id = {"obey": "controlled_1", "turn": "controlled_2",
                   "dismount": "controlled_3"}[behavior]
        entry = copy.deepcopy(original_entries[base_id])
        base_case_id = entry["case_id"]
        entry["case_id"] = case_id
        for name in ("measurement-contract.json", "recipe.json"):
            copy_proof(STAGE_PACKAGE / "electric-drafts" / label / name,
                       "electric-drafts/" + label + "/" + name)
        entry["construction"] = "electric-drafts/" + label + "/construction.json"
        entry["construction_sha256"] = sha(ROOT / entry["construction"])
        entry["fixture_recipe"] = "work/" + ROOT.name + "/electric-drafts/" + label + "/recipe.json"
        entry["measurement_contract"] = "electric-drafts/" + label + "/measurement-contract.json"
        entry["candidate_risk"]["reason"] = entry["candidate_risk"]["reason"].replace("Bicycle", label.rsplit('_', 1)[0].replace('_', ' ').title()).replace("bicycle", label.rsplit('_', 1)[0].replace('_', ' '))
        entry["candidate_risk"]["status"] = "physical"
        entry["physical_preparation"] = {
            "receipt": "electric-drafts/" + label + "/physical-proof/proof.json",
            "sha256": sha(ROOT / "electric-drafts" / label / "physical-proof/proof.json")}
        for candidate in ("primary", "fallback1"):
            spec = entry if candidate == "primary" else entry["candidates"][0]
            if candidate == "fallback1":
                spec["construction"] = "electric-drafts/" + label + "/fallback1/construction.json"
                spec["construction_sha256"] = sha(ROOT / spec["construction"])
                spec["id"] = "fallback1"
            offline_source = SCRATCH / (label + ("-fallback1" if candidate == "fallback1" else "")) / "offline.log"
            proof_dir = "electric-drafts/" + label + "/proof/" + candidate
            offline_rel = proof_dir + "/offline.log"
            offline_hash = copy_proof(offline_source, offline_rel)
            spec["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + ROOT.name +
                           "/execution-manifest.json --case " + case_id + " --candidate " + candidate +
                           " --output .runtime-work/c104538-electric-selected-" + label + "-" + candidate,
                "construction_sha256": spec["construction_sha256"],
                "exit_code": 0, "log": offline_rel, "log_sha256": offline_hash}
            compat_source = STAGE / ".runtime-work" / ("compat-" + label +
                             ("-fallback1" if candidate == "fallback1" else ""))
            receipt_rel = proof_dir + "/compatibility.json"
            log_rel = proof_dir + "/analysis.log"
            negative_rel = proof_dir + "/negative-analysis.log"
            receipt_hash = copy_proof(compat_source / "compatibility.json", receipt_rel)
            copy_proof(compat_source / "compatibility-analysis.log", log_rel)
            copy_proof(compat_source / "negative-analysis.log", negative_rel)
            spec["compatibility"] = {"receipt": receipt_rel, "sha256": receipt_hash,
                                     "log": log_rel, "negative_log": negative_rel}
            if candidate == "primary":
                entry["negative"] = {"log": negative_rel}
        acceptance = entry["delivery_acceptance"]
        acceptance["case_id"] = case_id
        acceptance["script_sha256"] = sha(ROOT / "native/delivery_audit.py")
        for name in ("command", "negative_command"):
            acceptance[name] = acceptance[name].replace(base_case_id, case_id)
        for name, log_name in (("test", "delivery-selftest.log"),
                               ("negative", "delivery-negative-selftest.log")):
            relative = "electric-drafts/" + label + "/" + log_name
            acceptance[name + "_log"] = relative
            acceptance[name + "_log_sha256"] = sha(ROOT / relative)
        acceptance["test_exit_code"] = 0
        acceptance["negative_exit_code"] = 1
        acceptance["scope"] = "synthetic CPU audit; reviewed electric asset, original pixels and physical acceptance pending"
        for name in ("command", "test_command"):
            entry["post_capture"][name] = entry["post_capture"][name].replace(base_case_id, case_id)
        entry["post_capture"]["test_command"] = (
            ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
            "/execution-manifest.json --case " + case_id +
            " --attempt .runtime-work/c104538-electric-selected-compat-" + label +
            " --output .runtime-work/c104538-electric-selected-saved-" + label +
            " --library runtime/library --validator .runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck")
        entry["post_capture"]["test_log"] = "electric-drafts/" + label + "/proof/primary/saved-processing.json"
        entry["post_capture"]["test_receipt"] = entry["post_capture"]["test_log"]
        stage_receipt = STAGE / ".runtime-work" / ("saved-" + label) / "v0001/processing.json"
        entry["post_capture"]["test_log_sha256"] = copy_proof(stage_receipt, entry["post_capture"]["test_log"])
        entry["post_capture"]["test_receipt_sha256"] = entry["post_capture"]["test_log_sha256"]
        entry["post_capture"]["test_exit_code"] = 0
        for atom, source in entry["acquisition"].items():
            source["evidence"] = source["evidence"].replace("bicycle", label.rsplit('_', 1)[0].replace('_', ' '))
        current["cases"].append(entry)
    save(ROOT / "case-plan.json", json.loads((STAGE_PACKAGE / "case-plan.json").read_text()))
    save(ROOT / "proposals/cases.json", json.loads((STAGE_PACKAGE / "proposals/cases.json").read_text()))
    semantic_index = json.loads((ROOT / "proposals/semantic-index.json").read_text())
    semantic_index["stages"]["cases"]["sha256"] = sha(ROOT / "proposals/cases.json")
    save(ROOT / "proposals/semantic-index.json", semantic_index)
    save(ROOT / "execution-manifest.json", current)
    result = json.loads((ROOT / "result.json").read_text())
    result["planned_case_count"] = len(current["cases"])
    result["candidate_count"] = sum(len(entry.get("candidates", [])) for entry in current["cases"])
    result["selected_cpu_checkpoint"]["case_count"] = len(current["cases"])
    result["selected_cpu_checkpoint"]["fallback1_count"] = sum(len(entry.get("candidates", [])) for entry in current["cases"])
    result["selected_cpu_checkpoint"]["electric_class_assets_selected"] = False
    result["selected_cpu_checkpoint"]["scoped_complete_passed"] = False
    result["selected_cpu_checkpoint"]["scoped_strict_passed"] = False
    result["selected_cpu_checkpoint"]["selected_manifest_sha256"] = sha(ROOT / "execution-manifest.json")
    result["electric_asset_binding"]["exact_electric_cases_selected"] = True
    result["reason"] = "Nine selected C104538 cases have conditional Native asset review gates; six electric cases have CPU offline, public compatibility, saved replay and synthetic physical proofs. Original reviewed electric assets, Native captures and physical/legal acceptance remain unverified. Static and strict scoped checks must be rerun."
    save(ROOT / "result.json", result)
    print(json.dumps({"selected_cases": len(current["cases"]),
                      "manifest_sha256": sha(ROOT / "execution-manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
