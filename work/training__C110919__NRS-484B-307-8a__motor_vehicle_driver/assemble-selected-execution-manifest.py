"""Bind twenty selected constructions to retained exact CPU proof sources.

This intentionally leaves physical outcome and delivery-acceptance receipts for
their own independent CPU tests. It does not claim delivery readiness.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "selected_delivery_receipts"
SOURCES = (
    ("update058-selected-ordinary-manifest.json",
     "update058-selected-ordinary-matrix-index.json",
     ".runtime-work/c110919-update058-selected-ordinary-matrix",
     "selected_ordinary_cases/receipts", True),
    ("update057-qualified-sweep-manifest.json",
     "update057-qualified-sweep-matrix-index.json",
     ".runtime-work/c110919-update057-qualified-matrix",
     "qualified_sweep_cases/receipts", False),
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_text(source, target):
    if not source.is_file():
        raise ValueError("Missing exact proof source: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return str(target.relative_to(HERE))


def bind_proof(entry, name, ref, manifest_path, run, source_log, ordinary):
    cid = entry["case_id"]
    suffix = cid.removeprefix(HERE.name + "__")
    destination = OUT / suffix / name
    offline_source = source_log / "offline.log"
    compat = run / "compatibility"
    saved = run / "saved/v0001/processing.json"
    offline_log = copy_text(offline_source, destination / "offline.log")
    compat_receipt = copy_text(compat / "compatibility.json", destination / "compatibility.json")
    analysis_log = copy_text(compat / "compatibility-analysis.log", destination / "compatibility-analysis.log")
    negative_log = copy_text(compat / "negative-analysis.log", destination / "negative-analysis.log")
    saved_receipt = copy_text(saved, destination / "processing.json")
    proof = read(HERE / compat_receipt)
    processed = read(HERE / saved_receipt)
    if (proof["passed"] is not True or proof["case_id"] != cid or
            proof["candidate_id"] != name or
            proof["construction_sha256"] != ref["construction_sha256"] or
            proof["log_sha256"] != sha(HERE / analysis_log) or
            proof["negative_log_sha256"] != sha(HERE / negative_log) or
            processed["passed"] is not True or processed["originals_preserved"] is not True or
            processed["physical_acceptance_claimed"] is not False):
        raise ValueError("Selected exact CPU receipts differ")
    command = (f"{sys.executable} runtime.py offline --manifest work/{HERE.name}/"
               f"{manifest_path.name} --case {cid} --candidate {name}"
               f" --output .runtime-work/{'c110919-update058-selected-ordinary-matrix' if ordinary else 'c110919-update057-qualified-matrix'}"
               f"/{sha(manifest_path)[:12]}/{suffix if ordinary else cid}/{name}/offline"
               f" --python {sys.executable}")
    ref["offline"] = {"command": command, "exit_code": 0,
                      "construction_sha256": ref["construction_sha256"],
                      "log": offline_log, "log_sha256": sha(HERE / offline_log)}
    ref["compatibility"] = {"receipt": compat_receipt,
                            "sha256": sha(HERE / compat_receipt),
                            "log": analysis_log, "negative_log": negative_log}
    ref["negative"] = {"log": negative_log}
    ref["saved_processing"] = {"receipt": saved_receipt,
                               "sha256": sha(HERE / saved_receipt)}


def main():
    output = {"format": "worker-execution-manifest",
              "assignment_id": HERE.name,
              "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
              "status": "selected_cpu_partial", "cases": []}
    for manifest_name, index_name, run_name, log_name, ordinary in SOURCES:
        manifest_path = HERE / manifest_name
        source = read(manifest_path)
        index = read(HERE / index_name)
        if index["manifest_sha256"] != sha(manifest_path) or len(index["results"]) != 40:
            raise ValueError("Exact selected CPU matrix missing")
        indexed = {(x["case_id"], x["candidate_id"]) for x in index["results"]}
        run_root = ROOT / run_name / sha(manifest_path)[:12]
        for source_entry in source["cases"]:
            entry = copy.deepcopy(source_entry)
            cid = entry["case_id"]
            suffix = cid.removeprefix(HERE.name + "__")
            entry["kind"] = "delivery"
            for name, ref in [("primary", entry), *[(c["id"], c) for c in entry["candidates"]]]:
                if (cid, name) not in indexed:
                    raise ValueError("Unproved selected candidate")
                run = run_root / (suffix if ordinary else cid) / name
                source_log = HERE / log_name / (suffix if ordinary else cid) / name
                bind_proof(entry, name, ref, manifest_path, run, source_log, ordinary)
            package = read(HERE / entry["construction"])
            config = json.loads(next(x["content"] for x in package["files"]
                                     if x["path"] == "config.json"))
            required = set(config.get("required_atoms", [])) | {
                x["name"] for x in package["recording_description"]["channels"]}
            entry["acquisition"] = {
                name: {"entrypoint": "runner.py" if name in config.get("required_atoms", []) else "finalize.py",
                       "method": "Original Native frame capture" if name in config.get("required_atoms", [])
                       else "Derived from retained original Native frame and camera sources",
                       "evidence": ["native_samples.jsonl", "road_geometry.json",
                                    "video_frames.jsonl"]}
                for name in sorted(required)}
            entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                       "host_env_var": "CARLA_HOST",
                                       "port_env_var": "CARLA_PORT"}
            output["cases"].append(entry)
    if len(output["cases"]) != 20:
        raise ValueError("Twenty selected cases required")
    path = HERE / "execution-manifest.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(output["cases"]),
                      "exact_cpu_candidates": 80,
                      "manifest_sha256": sha(path),
                      "delivery_ready": False}))


if __name__ == "__main__":
    main()
