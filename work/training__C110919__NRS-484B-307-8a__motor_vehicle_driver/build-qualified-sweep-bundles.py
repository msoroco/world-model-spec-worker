"""Rebind previously probed synthetic sweep bundles to selected exact case IDs."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "qualified_sweep_cases"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    stage_path = HERE / "proposals/cases.json"
    stage = read(stage_path)
    cases = {case["case_id"]: case for case in stage["cases"] if case.get("sweep_id")}
    if len(cases) != 10 or not all(cid.startswith(HERE.name + "__") for cid in cases):
        raise ValueError("Canonical qualified sweep stage differs")
    manifests = [read(HERE / name) for name in (
        "update041-traffic-timing-sweep-manifest.json",
        "update052-extreme-right-sweep-manifest.json")]
    output = {"format": "c110919-qualified-sweep-exact-candidates-v1",
              "assignment_id": HERE.name, "stage_sha256": sha(stage_path),
              "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
              "status": "selected_cpu_unproved", "cases": []}
    for manifest in manifests:
        for old in manifest["cases"]:
            cid = HERE.name + "__" + old["case_id"]
            case = cases[cid]
            entry = copy.deepcopy(old)
            entry["case_id"] = cid
            entry["candidate_risk"]["status"] = "physical"
            old_recipe = read(ROOT / old["fixture_recipe"])
            diagnostic_path = ROOT / old_recipe["generator"]["source"]
            if sha(diagnostic_path) != old_recipe["generator"]["sha256"]:
                raise ValueError("Historical diagnostic source changed")
            recipe_path = OUT / cid / "fixture-recipe.json"
            save(recipe_path, old_recipe)
            entry["fixture_recipe"] = str(recipe_path.relative_to(ROOT))
            contract = read(HERE / old["measurement_contract"])
            contract["case_id"] = cid
            contract_path = OUT / cid / "measurement-contract.json"
            save(contract_path, contract)
            entry["measurement_contract"] = str(contract_path.relative_to(HERE))
            for name, ref in [("primary", entry), *[(c["id"], c) for c in entry["candidates"]]]:
                old_path = HERE / ref["construction"]
                if sha(old_path) != ref["construction_sha256"]:
                    raise ValueError("Historical construction changed")
                package = read(old_path)
                package["case_id"] = cid
                package["status"] = "selected_cpu_unproved"
                package["recording_description"] = case["recording_description"]
                files = {item["path"]: item["content"] for item in package["files"]}
                config = json.loads(files["config.json"])
                config.update({"case_id": cid, "selected_case_id": cid,
                               "supported_case_ids": [cid], "case": case,
                               "recording_description": case["recording_description"]})
                files["config.json"] = json.dumps(config, indent=2) + "\n"
                package["files"] = [{"path": path, "content": content}
                                    for path, content in files.items()]
                target = OUT / cid / name / "construction.json"
                save(target, package)
                ref["construction"] = str(target.relative_to(HERE))
                ref["construction_sha256"] = sha(target)
            output["cases"].append(entry)
    if set(c["case_id"] for c in output["cases"]) != set(cases):
        raise ValueError("Qualified package coverage differs")
    manifest_path = HERE / "update057-qualified-sweep-manifest.json"
    save(manifest_path, output)
    print(json.dumps({"qualified_cases": len(output["cases"]),
                      "bundles": sum(1 + len(c["candidates"]) for c in output["cases"]),
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
