"""Bind four proven alternative constructions into the selected six-case package."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
CASES = PACKAGE / "cases"
LABELS = ("intersection-entry", "intersection-stop", "corner-entry", "corner-stop")
COMPAT = ("intersection", "intersection-stop", "corner-entry", "corner-stop")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrate():
    selected = read(PACKAGE / "execution-manifest.json")
    if len(selected.get("cases", [])) == 6:
        print("Six exact cases already selected; preserving their later proof revisions")
        return
    staged = read(CASES / "alternative-offline-manifest.json")
    compatibility = read(CASES / "alternative-full-compatibility-index.json")
    saved = read(CASES / "alternative-full-saved-processing-index.json")
    physical = read(CASES / "alternative-physical-index.json")
    delivery = read(CASES / "alternative-delivery-index.json")
    if len(selected["cases"]) not in (2, 6) or len(staged["cases"]) != 4:
        raise ValueError("Selected or staged case count changed")
    previous = {row["case_id"]: row for row in selected["cases"]}
    if len(compatibility["cases"]) != len(saved["cases"]) != len(physical["cases"]) != len(delivery["cases"]) != 4:
        raise ValueError("Four alternative proof families required")
    baseline = [e for e in selected["cases"] if "crosswalk" in e["case_id"]]
    if len(baseline) != 2:
        raise ValueError("Selected crosswalk pair changed")
    template = baseline[0]
    extra = []
    for i, draft in enumerate(staged["cases"]):
        ident = draft["case_id"]
        if ident != compatibility["cases"][i]["case_id"] or ident != saved["cases"][i]["case_id"] or ident != physical["cases"][i]["case_id"] or ident != delivery["cases"][i]["case_id"]:
            raise ValueError("Alternative proof order or identity changed")
        label, compat_label = LABELS[i], COMPAT[i]
        construction_path = CASES / draft["construction"]
        if sha(construction_path) != draft["construction_sha256"]:
            raise ValueError("Alternative construction changed")
        compat_receipt = CASES / (compat_label + "-full-compatibility-receipt.json")
        negative = CASES / (compat_label + "-full-negative-analysis.log")
        if sha(compat_receipt) != compatibility["cases"][i]["receipt_sha256"]:
            raise ValueError("Alternative compatibility receipt changed")
        item = {
            "case_id": ident,
            "kind": "delivery",
            "construction": "cases/" + draft["construction"],
            "construction_sha256": draft["construction_sha256"],
            "measurement_procedure": draft["measurement_procedure"],
            "candidate_risk": {"status": "physical", "reason": "Native site, reverse path and four camera views require original-source review"},
            "candidates": previous.get(ident, {}).get("candidates", []),
            "measurement_contract": "cases/" + draft["measurement_contract"],
            "fixture_recipe": "work/" + PACKAGE.name + "/cases/" + compatibility["cases"][i]["fixture_recipe"],
            "acquisition": {**template["acquisition"],
                            "st.intersection": {"entrypoint": "runner.py",
                                                "method": "original Native map and intersection region source readback",
                                                "evidence": "reverse_site_context.json and capture/native/graphs"},
                            "region_overlap": {"entrypoint": "runner.py",
                                               "method": "original Native complete-body geometry and sourced region frame join",
                                               "evidence": "reverse_history.jsonl and reverse_site_context.json"}},
            "offline": {**draft["offline"], "log": "cases/" + draft["offline"]["log"]},
            "compatibility": {"command": ".venv-cpu/bin/python runtime.py compatibility --manifest .runtime-work/c215286-intersection-stage/manifest.json --case " + ident + " --output .runtime-work/" + ("c215286-alt-intersection-compat-v4", "c215286-alt-intersection-stop-compat", "c215286-alt-corner-entry-compat-v3", "c215286-alt-corner-stop-compat")[i] + " --library runtime/library --validator .runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck",
                              "receipt": "cases/" + compat_receipt.name, "sha256": sha(compat_receipt),
                              "log": "cases/" + compat_label + "-full-compatibility-analysis.log",
                              "negative_log": "cases/" + negative.name,
                              "negative_log_sha256": sha(negative)},
            "saved_processing": {"command": ".venv-cpu/bin/python runtime.py process-saved --manifest .runtime-work/c215286-intersection-stage/manifest.json --case " + ident + " --attempt .runtime-work/c215286-alt-" + label + "-saved-source --output .runtime-work/c215286-alt-" + label + "-saved-full --library runtime/library --validator .runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck",
                                 "receipt": "cases/" + saved["cases"][i]["receipt"],
                                 "sha256": saved["cases"][i]["receipt_sha256"],
                                 "log": "cases/" + saved["cases"][i]["log"],
                                 "log_sha256": saved["cases"][i]["log_sha256"]},
            "negative": {"log": "cases/" + negative.name, "sha256": sha(negative)},
            "physical_preparation": {"receipt": physical["cases"][i]["receipt"],
                                     "sha256": physical["cases"][i]["sha256"]},
            "native_handoff": {**template["native_handoff"],
                               "source_preflight_command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-native-preflight PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + PACKAGE.name + "/reverse_alternative_capture.py --check",
                               "case_id": ident},
            "delivery_acceptance": {
                "case_id": ident, "sets": ["demo-test", "full-test"],
                "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                           "actual_pixels", "physical_completion"],
                "script": "reverse_alternative_delivery_audit.py",
                "script_sha256": sha(PACKAGE / "reverse_alternative_delivery_audit.py"),
                "auditor": "reverse_alternative_delivery_audit.py",
                "auditor_sha256": sha(PACKAGE / "reverse_alternative_delivery_audit.py"),
                "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-alternative-delivery " + delivery["cases"][i]["positive_command"],
                "test_exit_code": 0, "test_log": delivery["cases"][i]["positive_log"],
                "test_log_sha256": delivery["cases"][i]["positive_log_sha256"],
                "negative_command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-alternative-delivery " + delivery["cases"][i]["negative_command"],
                "negative_exit_code": 1, "negative_expected_error": delivery["cases"][i]["negative_expected_error"],
                "negative_log": delivery["cases"][i]["negative_log"],
                "negative_log_sha256": delivery["cases"][i]["negative_log_sha256"],
                "proof_scope": "900-frame synthetic software boundary; original Native source, pixels and legal outcome unaccepted",
            },
        }
        extra.append(item)
    selected["cases"] = baseline + extra
    comparisons = selected["comparisons"][:1]
    for row in staged["comparisons"]:
        comparisons.append({**row, "receipt": "cases/" + row["receipt"]})
    selected["comparisons"] = comparisons
    plan = read(CASES / "alternative-selected-case-plan.json")
    plan["planning_status"] = "selected six-case CPU package; Native site and camera review pending"
    proposals = read(CASES / "alternative-selected-proposals.json")
    write(PACKAGE / "case-plan.json", plan)
    write(PACKAGE / "proposals/cases.json", proposals)
    write(PACKAGE / "execution-manifest.json", selected)
    print("Selected", len(selected["cases"]), "cases and", len(comparisons), "comparisons")


if __name__ == "__main__":
    integrate()
