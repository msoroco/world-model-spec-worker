"""Complete ordinary capture context and rebuild exact selected CPU bundles."""
import copy
import hashlib
import json
from pathlib import Path
from selected_camera_contract import cameras

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "selected_ordinary_cases"


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
    sweep = next(c for c in stage["cases"] if c.get("sweep_id") == "C110919-right-of-way")
    needed = {x["name"]: x for x in sweep["recording_description"]["context_inputs"]
              if x["name"] in ("four_source_cameras", "surveyed_C110919_intersection")}
    if len(needed) != 2:
        raise ValueError("Native camera and intersection context definitions missing")
    ordinary = {c["case_id"]: c for c in stage["cases"] if not c.get("sweep_id")}
    if len(ordinary) != 11:
        raise ValueError("Ordinary and baseline case set differs")
    for case in ordinary.values():
        contexts = case["recording_description"]["context_inputs"]
        have = {x["name"] for x in contexts}
        for name in ("four_source_cameras", "surveyed_C110919_intersection"):
            if name not in have:
                contexts.append(copy.deepcopy(needed[name]))
    save(stage_path, stage)
    source = read(HERE / "update038-ten-case-probe-manifest.json")
    manifest = {"format": "c110919-selected-ordinary-exact-bundles-v1",
                "assignment_id": HERE.name,
                "stage_sha256": sha(stage_path),
                "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
                "status": "selected_cpu_unproved", "cases": []}
    for old in source["cases"]:
        cid = old["case_id"]
        case = ordinary[cid]
        entry = copy.deepcopy(old)
        entry.pop("preparation_status", None)
        suffix = cid.removeprefix(HERE.name + "__")
        contract = copy.deepcopy(read(HERE / old["measurement_contract"]))
        if suffix in ("absent_reference", "absent_reference_contrast",
                      "green_release_wait", "green_release_red_turn"):
            disposition = next(d for d in read(HERE / "case-plan.json")["requirement_dispositions"]
                               if d["requirement"] == "text-1")
            stop_row = next(r for r in contract["requirements"]
                            if r["output_key"] == "right_turn_stop")
            row = copy.deepcopy(stop_row)
            row.update({"disposition_index": 1, "requirement": "text-1",
                        "source": disposition["source"],
                        "output_key": "stop_boundary_alternative" if suffix.startswith("absent_reference")
                        else "green_release",
                        "method": "measure_stop" if suffix.startswith("absent_reference")
                        else "measure_green_release"})
            contract["requirements"].append(row)
        contract_path = OUT / suffix / "measurement-contract.json"
        save(contract_path, contract)
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
        finalizer = ("yield_branch_finalize.py" if suffix.startswith("yield_") else
                     "traffic_branch_finalize.py" if suffix.startswith("traffic_") else
                     "finalize.py")
        finalizer_code = (HERE / "native" / finalizer).read_text()
        for name, ref in [("primary", entry), *[(c["id"], c) for c in entry["candidates"]]]:
            old_path = HERE / ref["construction"]
            if sha(old_path) != ref["construction_sha256"]:
                raise ValueError("Historical ordinary construction changed")
            package = read(old_path)
            package["recording_description"] = case["recording_description"]
            files = {item["path"]: item["content"] for item in package["files"]}
            config = json.loads(files["config.json"])
            config["case"] = case
            config["recording_description"] = case["recording_description"]
            config["cameras"] = cameras()
            files["config.json"] = json.dumps(config, indent=2) + "\n"
            files["finalize.py"] = finalizer_code
            package["files"] = [{"path": path, "content": content}
                                for path, content in files.items()]
            path = OUT / suffix / name / "construction.json"
            save(path, package)
            ref["construction"] = str(path.relative_to(HERE))
            ref["construction_sha256"] = sha(path)
        manifest["cases"].append(entry)
    target = HERE / "update058-selected-ordinary-manifest.json"
    save(target, manifest)
    index_path = HERE / "proposals/semantic-index.json"
    index = read(index_path)
    index["stages"]["cases"]["sha256"] = sha(stage_path)
    save(index_path, index)
    print(json.dumps({"ordinary_cases": len(manifest["cases"]),
                      "candidate_bundles": 4 * len(manifest["cases"]),
                      "manifest_sha256": sha(target),
                      "stage_sha256": sha(stage_path)}))


if __name__ == "__main__":
    main()
