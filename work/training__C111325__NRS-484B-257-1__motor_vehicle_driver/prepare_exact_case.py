"""Prepare a source-bound exact case bundle from an authored diagnostic packet."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare(slug):
    source = HERE / "selected-source" / slug
    if not source.is_dir():
        raise ValueError("Materialize exact diagnostic source first")
    case = BASE + slug
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if any(entry["case_id"] == case for entry in manifest["cases"]):
        raise ValueError("Exact case already selected")
    config = json.loads((HERE / "config.json").read_text())
    config["selected_case_id"] = case
    config["case"]["case_id"] = case
    config_path = HERE / ("config-" + slug + ".json")
    save(config_path, config)
    test = (HERE / "test_native_capture.py").read_text()
    test = test.replace('result["selected_case_id"], case_id("complete_stop_then_yield")',
                        'result["selected_case_id"], case_id("' + slug + '")')
    test_path = HERE / ("test_native_capture_" + slug + ".py")
    test_path.write_text(test)
    plan = json.loads((HERE / "case-plan.json").read_text())
    contract = json.loads((HERE / "measurement-complete_stop_then_yield.json").read_text())
    contract["case_id"] = case
    contract["requirements"] = [r for r in contract["requirements"] if case in
                                plan["requirement_dispositions"][r["disposition_index"]]["case_ids"]]
    needs_reference_negative = not any("governing_sign.json" in r["inputs"]
                                       for r in contract["requirements"])
    constructions = []
    for candidate, original in (("primary", "construction.json"),
                                ("fallback1", "construction-fallback1.json")):
        value = json.loads((HERE / original).read_text())
        value["case_id"] = case
        for item in value["files"]:
            if item["path"] == "config.json":
                item["content"] = config_path.read_text()
                item["source"] = str(config_path.relative_to(REPO))
            if item["path"] == "tests/test_native_capture.py":
                item["content"] = test
                item["source"] = str(test_path.relative_to(REPO))
            if item["path"] == "finalize.py" and needs_reference_negative:
                finalizer = HERE / "finalize_yield.py"
                item["content"] = finalizer.read_text()
                item["source"] = str(finalizer.relative_to(REPO))
        name = "construction-" + slug + ("" if candidate == "primary" else "-fallback1") + ".json"
        output = HERE / name
        save(output, value)
        constructions.append((name, sha(output)))
    if needs_reference_negative:
        contract["negative"] = {"remove": ["stopping_reference.json"],
                                "error_contains": "Missing required source: stopping_reference.json"}
    contract_name = "measurement-" + slug + ".json"
    save(HERE / contract_name, contract)
    recipe = json.loads((HERE / "selected-recipe-complete_stop_then_yield.json").read_text())
    for item in recipe["sources"]:
        item["source"] = str((source / item["path"]).relative_to(REPO))
        item["sha256"] = sha(source / item["path"])
    recipe_name = "selected-recipe-" + slug + ".json"
    save(HERE / recipe_name, recipe)
    entry = {"case_id": case, "kind": "delivery", "construction": constructions[0][0],
             "construction_sha256": constructions[0][1],
             "candidate_risk": {"status": "physical", "reason":
                                "Original Native sign pixels and reference visibility need local review"},
             "candidates": [{"id": "fallback1", "construction": constructions[1][0],
                             "construction_sha256": constructions[1][1],
                             "trigger": {"source": "original Native first-capture camera review",
                                         "metric": "governing sign actual-pixel visibility in overview and reference_corner",
                                         "failure_condition": "governing sign unreadable or occluded in either required source view"},
                             "changed_knobs": ["overview fixed-world camera position/pitch/yaw",
                                               "reference_corner fixed-world camera position/pitch/yaw"]}],
             "delivery_readiness": "incomplete", "measurement_contract": contract_name,
             "fixture_recipe": str((HERE / recipe_name).relative_to(REPO)),
             "measurement_procedure": {"entrypoint": "finalize.py",
                                       "output_schema": "nrs-484b-257-1-selected-analysis-v1"},
             "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}}
    manifest["cases"].append(entry)
    save(manifest_path, manifest)
    print(json.dumps({"case_id": case, "candidate_count": 2,
                      "diagnostic_only": True}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    prepare(parser.parse_args().slug)
