"""Build five exact unselected timing-sweep cases with four candidate bundles."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
OUT = HERE / "traffic_timing_sweep_cases"
sys.path.insert(0, str(HERE / "native"))
from traffic_timing_sweep import TrafficLaunch, intersects


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    stage_path = HERE / "proposals/right-of-way-sweep-candidate.json"
    stage = read(stage_path)
    source_manifest = read(HERE / "draft-traffic-branch-execution-manifest.json")
    source = next(x for x in source_manifest["cases"] if
                  x["case_id"].endswith("__traffic_yield_wait"))
    base_diagnostic = read(HERE / "traffic_branch_cases/traffic_yield_wait-diagnostic.json")
    base_native = [json.loads(line) for line in
                   base_diagnostic["files"]["native_samples.jsonl"].splitlines()]
    if len(base_native) != 480:
        raise ValueError("Source diagnostic has no 480-frame Native stream")
    by_candidate = {x["id"]: x for x in source["candidates"]}
    by_candidate["primary"] = {"id": "primary", "construction": source["construction"],
                               "construction_sha256": source["construction_sha256"]}
    cases = [c for c in stage["cases"] if c.get("sweep_id") == "C110919-right-of-way"]
    if len(cases) != 5 or stage.get("candidate_only") is not True:
        raise ValueError("Candidate stage or exact sweep case set differs")
    native = HERE / "native"
    replacement = {
        "runner.py": "traffic_timing_sweep_runner.py",
        "finalize.py": "traffic_timing_sweep_finalize.py",
        "traffic_timing_sweep.py": "traffic_timing_sweep.py",
    }
    manifest = {
        "format": "c110919-timing-sweep-exact-candidates-v1",
        "assignment_id": HERE.name,
        "stage_sha256": sha(stage_path),
        "runtime_manifest_sha256": sha(HERE.parents[1] / "runtime/pipeline/SOURCE-MANIFEST.json"),
        "status": "unselected_cpu_candidate",
        "cases": [],
    }
    for case in cases:
        ident = case["case_id"]
        frame = TrafficLaunch(case["sweep_point"]["traffic_launch_frame"]).start_frame
        diagnostic = deepcopy(base_diagnostic)
        native_rows = []
        for index, baseline in enumerate(base_native):
            row = deepcopy(baseline)
            source_index = min(479, max(0, index - (frame - 30)))
            traffic = base_native[source_index]
            for key in ("other_traffic_center_xy_m", "other_traffic_body_xy_m",
                        "other_traffic_speed_mps"):
                row[key] = deepcopy(traffic[key])
            row["traffic_conflict_occupied"] = intersects(row["other_traffic_body_xy_m"])
            row["traffic_launch_frame"] = frame
            native_rows.append(row)
        diagnostic["files"]["native_samples.jsonl"] = "\n".join(
            json.dumps(row, separators=(",", ":")) for row in native_rows) + "\n"
        diagnostic_path = OUT / ident / "diagnostic.json"
        save(diagnostic_path, diagnostic)
        diagnostic_source = str(diagnostic_path.relative_to(ROOT := HERE.parents[1]))
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": diagnostic_source,
                               "sha256": sha(diagnostic_path)}],
                  "generator": {"source": diagnostic_source,
                                "sha256": sha(diagnostic_path)}}
        recipe_path = OUT / ident / "fixture-recipe.json"
        save(recipe_path, recipe)
        entry = {
            "case_id": ident,
            "sweep_id": "C110919-right-of-way",
            "authored_traffic_launch_frame": frame,
            "candidate_risk": {
                "status": "physical",
                "reason": "Original directed traffic and ego timing, full-body paths and four-camera pixels require Native review",
            },
            "fixture_recipe": str(recipe_path.relative_to(ROOT)),
            "measurement_procedure": {
                "entrypoint": "finalize.py",
                "output_schema": "c110919-saved-analysis-v1",
            },
            "candidates": [],
        }
        contract = deepcopy(read(HERE / source["measurement_contract"]))
        contract["case_id"] = ident
        contract_path = OUT / ident / "measurement-contract.json"
        save(contract_path, contract)
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
        for name in ("primary", "fallback1", "fallback2", "fallback3"):
            base_ref = by_candidate[name]
            path = HERE / base_ref["construction"]
            if sha(path) != base_ref["construction_sha256"]:
                raise ValueError("Original traffic candidate construction changed")
            construction = deepcopy(read(path))
            files = {f["path"]: f["content"] for f in construction["files"]}
            config = json.loads(files["config.json"])
            config.update({
                "case_id": ident, "selected_case_id": ident,
                "supported_case_ids": [ident], "sweep_id": "C110919-right-of-way",
                "traffic_launch_frame": frame, "case_suffix": "traffic_yield_wait",
                "case": case, "recording_description": case["recording_description"],
            })
            files["config.json"] = json.dumps(config, indent=2) + "\n"
            for target, source_name in replacement.items():
                files[target] = (native / source_name).read_text()
            construction.update({
                "case_id": ident,
                "files": [{"path": key, "content": value} for key, value in files.items()],
                "recording_description": case["recording_description"],
                "mechanisms": [
                    "Fixed ego red-turn yield controller and authored cross-traffic launch frame",
                    "Separate directed cross-traffic green and surveyed west-approach lane",
                    "480 Native full-body/signal rows and four joined source cameras",
                ],
                "status": "unselected_cpu_candidate",
            })
            output = OUT / ident / name / "construction.json"
            save(output, construction)
            ref = {"id": name, "construction": str(output.relative_to(HERE)),
                   "construction_sha256": sha(output)}
            if name == "primary":
                entry.update({k: ref[k] for k in ("construction", "construction_sha256")})
            else:
                if name == "fallback2":
                    ref.update(trigger={
                        "source": "original Native full-body traffic and ego conflict timing",
                        "metric": "observed_ego_minus_traffic_entry_s",
                        "failure_condition": "invalid or physically unsafe overlap after selected timing launch",
                    }, changed_knobs=["yield_clearance_margin_s"])
                else:
                    ref.update(trigger=base_ref["trigger"],
                               changed_knobs=base_ref["changed_knobs"])
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    manifest_path = HERE / "update041-traffic-timing-sweep-manifest.json"
    save(manifest_path, manifest)
    print(json.dumps({"exact_cases": len(cases), "candidate_bundles": 4 * len(cases),
                      "manifest_sha256": sha(manifest_path), "selected": False}))


if __name__ == "__main__":
    main()
