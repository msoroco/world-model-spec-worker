"""Bind repaired right-only constructions and existing current CPU proofs."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/lead-c382389"
COMPAT = {
    ("reference", "primary"): "reference-primary-public-v4",
    ("reference", "fallback1"): "reference-fallback1-public",
    ("reference", "fallback2"): "reference-fallback2-compat-1795548891576905263",
    ("reference", "fallback3"): "reference-fallback3-compat-1795548891577147719",
    ("contrast", "primary"): "contrast-primary-public",
    ("contrast", "fallback1"): "contrast-fallback1-public",
    ("contrast", "fallback2"): "contrast-fallback2-compat-1795549010786339989",
    ("contrast", "fallback3"): "contrast-fallback3-compat-1795549062090937140",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def copy_text(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text().rstrip() + "\n"
    target.write_text(content)
    return sha(target)


def proof(label, candidate, construction_hash):
    folder = HERE / "selected-proof" / label / candidate
    folder.mkdir(parents=True, exist_ok=True)
    original = SCRATCH / COMPAT[(label, candidate)]
    receipt = original / "compatibility.json"
    if not receipt.is_file():
        raise FileNotFoundError(receipt)
    data = json.loads(receipt.read_text())
    assert data["construction_sha256"] == construction_hash
    assert data["candidate_id"] == candidate
    paths = {"receipt": "compatibility.json", "log": "compatibility-analysis.log",
             "negative_log": "negative-analysis.log"}
    result = {}
    for key, name in paths.items():
        source = original / name
        target = folder / ("analysis.log" if key == "log" else name)
        result[key] = str(target.relative_to(HERE))
        result["sha256" if key == "receipt" else key + "_sha256"] = copy_text(source, target)
    assert data["log_sha256"] == result["log_sha256"]
    assert data["negative_log_sha256"] == result["negative_log_sha256"]
    return result


def offline(label, candidate, construction_hash, case_id):
    source = SCRATCH / f"offline-{label}-{candidate}" / "offline.log"
    target = HERE / "selected-proof" / label / candidate / "offline.log"
    copied = copy_text(source, target)
    matrix = json.loads((HERE / "current-offline-matrix-proof.json").read_text())
    row = next(item for item in matrix["candidates"] if item["case_id"] == case_id and item["candidate_id"] == candidate)
    assert row["construction_sha256"] == construction_hash
    assert row["offline_log_sha256"] == copied
    return {"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-diagnostic-manifest.json --case {case_id} --candidate {candidate} --output .runtime-work/lead-c382389/offline-{label}-{candidate} --python .venv-cpu/bin/python",
            "exit_code": 0, "construction_sha256": construction_hash,
            "log": str(target.relative_to(HERE)), "log_sha256": copied}


def main():
    diagnostic = json.loads((HERE / "current-diagnostic-manifest.json").read_text())
    selected = []
    for item in diagnostic["cases"]:
        case_id = item["case_id"]
        label = case_id.rsplit("__", 1)[-1]
        primary = HERE / item["construction"]
        construction = json.loads(primary.read_text())
        entry = {key: value for key, value in item.items() if key not in ("id", "candidates")}
        entry["kind"] = "delivery"
        entry["offline"] = offline(label, "primary", item["construction_sha256"], case_id)
        entry["compatibility"] = {key: value for key, value in proof(label, "primary", item["construction_sha256"]).items() if key in ("receipt", "sha256", "log", "negative_log")}
        entry["negative"] = {"log": entry["compatibility"]["negative_log"],
                             "log_sha256": sha(HERE / entry["compatibility"]["negative_log"]),
                             "expected_error": "Missing required source: native_samples.jsonl"}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        acquisition = {}
        for channel in construction["recording_description"]["channels"]:
            acquisition[channel["name"]] = {"entrypoint": "runner.py", "method": channel["method"],
                "evidence": "original Native frame, body, lane and synchronized camera timestamp"}
        for atom in json.loads(next(file["content"] for file in construction["files"] if file["path"] == "config.json"))["required_atoms"]:
            acquisition[atom] = {"entrypoint": "runner.py", "method": "Original Native pose and heading readback",
                                  "evidence": "original Native frame and 20 Hz timestamp"}
        entry["acquisition"] = acquisition
        candidates = []
        for candidate in item["candidates"]:
            if candidate["id"] == "fallback2":
                continue
            candidate = dict(candidate)
            ident = candidate["id"]
            candidate["offline"] = offline(label, ident, candidate["construction_sha256"], case_id)
            candidate["compatibility"] = {key: value for key, value in proof(label, ident, candidate["construction_sha256"]).items() if key in ("receipt", "sha256", "log", "negative_log")}
            candidates.append(candidate)
        entry["candidates"] = candidates
        selected.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": diagnostic["runtime_manifest_sha256"],
                "status": "selected_cpu_proofs_in_progress", "cases": selected}
    write(HERE / "execution-manifest.json", manifest)
    reference = json.loads((HERE / diagnostic["cases"][0]["construction"]).read_text())
    root_bundle = json.loads(json.dumps(reference))
    root_config = json.loads(next(file["content"] for file in root_bundle["files"] if file["path"] == "config.json"))
    root_config["supported_case_ids"] = [entry["case_id"] for entry in selected]
    for file in root_bundle["files"]:
        if file["path"] == "config.json":
            file["content"] = json.dumps(root_config, indent=2) + "\n"
        target = HERE / file["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file["content"].rstrip() + "\n")
        file["content"] = target.read_text()
    write(HERE / "construction.json", root_bundle)
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["selected_branch"] = "Straight traversal from a right-turn-lane approach"
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 24,
        "composition": "synchronized_four_view_primary", "coverage": [
            {"subject": "full ego body, turn-only lane arrow and intersection boundary",
             "interval": "all 480 frames", "view": view} for view in
            ("overview", "approach", "reference_corner", "driver_reference")]}
    for case in plan["cases"]:
        case["planning_status"] = "selected_delivery_cpu_prepared"
    names = {channel["name"] for channel in reference["recording_description"]["channels"]}
    plan["observations"] = [item for item in plan["observations"] if item["name"] not in names]
    for item in plan["observations"]:
        item["mandatory"] = False
    for channel in reference["recording_description"]["channels"]:
        plan["observations"].append({"name": channel["name"], "unit": channel["unit"],
            "mandatory": True, "purpose": channel["method"]})
    for name, mapping in plan["source_observation_mapping"].items():
        mapping["channels"] = [name]
        mapping["evidence"] = "Original Native source channel, surveyed lane and full body crossing; physical designation and legal outcome require independent review"
    plan["requirement_dispositions"][0]["evidence_or_gap"] = "Both exact right-only lane comparison cases selected with source-bound current-runtime CPU diagnostics; original Native lane designation, physical crossing and legal outcome remain for independent local review."
    write(plan_path, plan)
    index = json.loads((HERE / "proposals/semantic-index.json").read_text())
    index["format"] = "worker-semantic-delivery"
    index["status"] = "draft_selected"
    write(HERE / "proposals/semantic-index.json", index)
    print(json.dumps({"selected_cases": len(selected), "selected_candidates": sum(len(row["candidates"]) for row in selected)}))


if __name__ == "__main__":
    main()
