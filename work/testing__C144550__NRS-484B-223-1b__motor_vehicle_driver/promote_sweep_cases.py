"""Bind CPU-proven zero and physical sweep cases into selected delivery files."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / ".runtime-work" / "c144550-physical-sweeps"


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def main():
    staged_cases = read(STAGE / "cases.json")
    generated = [case["case_id"] for case in staged_cases["cases"] if case.get("sweep_id")]
    zero = HERE.name + "__left_signal_at_departure_clear_gap"
    additions = [zero, *generated]
    assert len(additions) == 6 and len(set(additions)) == 6

    manifest = read(HERE / "execution-manifest.json")
    zero_manifest = read(HERE / "zero-execution-manifest.json")
    sweep_manifest = read(HERE / "sweep-execution-manifest.json")
    assert manifest["assignment_id"] == zero_manifest["assignment_id"] == sweep_manifest["assignment_id"]
    assert zero_manifest["runtime_manifest_sha256"] == sweep_manifest["runtime_manifest_sha256"]
    selected = {case["case_id"] for case in manifest["cases"]}
    assert not selected.intersection(additions)
    manifest["runtime_manifest_sha256"] = sweep_manifest["runtime_manifest_sha256"]
    for case in [*zero_manifest["cases"], *sweep_manifest["cases"]]:
        assert case["case_id"] in additions
        case["status"] = "selected_cpu_diagnostic_proven"
        manifest["cases"].append(case)
    write(HERE / "execution-manifest.json", manifest)

    for name in ("cases", "bindings", "template", "judgment-observables-1", "judgment-observables-2"):
        write(HERE / "proposals" / f"{name}.json", read(STAGE / f"{name}.json"))
    index_path = HERE / "proposals/semantic-index.json"
    index = read(index_path)
    for stage in index["stages"].values():
        entries = stage if isinstance(stage, list) else [stage]
        for entry in entries:
            path = HERE / entry["path"]
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(index_path, index)

    plan_path = HERE / "case-plan.json"
    plan = read(plan_path)
    disposition = plan["requirement_dispositions"][0]
    disposition["case_ids"] += additions
    plan["cases"] += [{"case_id": case_id, "target_law_id": plan["law_id"],
                       "purpose": "Source-bound zero-frame or finite physical sweep diagnostic; legal judgment unresolved",
                       "physical_risk": "Actual Native capture, road marking, display and traffic gap require review"}
                      for case_id in additions]
    plan["selected_zero_and_physical_sweeps_20261124"] = {
        "case_ids": additions,
        "proofs": ["zero-exact-candidate-replay.json", "sweep-candidate-replay.json"],
        "scope": "CPU diagnostics only; physical and legal acceptance unproved",
    }
    write(plan_path, plan)
    print(json.dumps({"selected_cases": len(manifest["cases"]), "new_cases": additions,
                      "runtime_manifest_sha256": manifest["runtime_manifest_sha256"]}))


if __name__ == "__main__":
    main()
