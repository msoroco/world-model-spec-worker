"""Stage static rail-at package fields while canonical delivery remains six cases."""
import hashlib
import json
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "runtime/pipeline"),
                str(ROOT / "runtime/pipeline/scenario_pipeline")]
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.physical_preparation import validate as validate_physical
from scenario_pipeline.worker_exchange.candidate_constructions import validate as validate_candidates


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = HERE / "update035-seven-case-probe-manifest.json"
manifest = read(source)
assert len(manifest["cases"]) == 7
entry = next(x for x in manifest["cases"] if x["case_id"].endswith("__rail_at"))
template = next(x for x in manifest["cases"] if x["case_id"].endswith("__rail_contrast"))
index = read(HERE / "update035-rail-at-retained-index.json")
assert index["manifest_sha256"] == sha(source) and index["candidate_count"] == 4
retained = {row["candidate_id"]: row for row in index["candidates"]}
for candidate in (entry, *entry["candidates"]):
    ident = candidate["id"]
    row = retained[ident]
    assert row["construction_sha256"] == candidate["construction_sha256"]
    base = HERE / "update035-probe-proofs/rail_at" / ident
    files = row["files"]
    candidate["offline"] = {
        "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry['case_id']} --candidate {ident} --output ${{OFFLINE_DIR}} --python .venv-cpu/bin/python",
        "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
        "log": str((base / "offline.log").relative_to(HERE)),
        "log_sha256": sha(base / "offline.log")}
    candidate["compatibility"] = {
        "receipt": files["compatibility.json"]["path"],
        "sha256": files["compatibility.json"]["sha256"],
        "log": files["compatibility-analysis.log"]["path"],
        "negative_log": files["negative-analysis.log"]["path"]}
negative = retained["primary"]["files"]["negative-analysis.log"]
entry["negative"] = {"log": negative["path"], "log_sha256": negative["sha256"]}
saved_log = HERE / "update035-probe-proofs/rail_at/primary/process-saved.log"
entry["post_capture"] = dict(template["post_capture"])
entry["post_capture"]["command"] = template["post_capture"]["command"].replace(
    template["case_id"], entry["case_id"])
entry["post_capture"]["test_log"] = str(saved_log.relative_to(HERE))
entry["post_capture"]["test_log_sha256"] = sha(saved_log)
entry["native_handoff"] = dict(template["native_handoff"])
acquisition = runpy.run_path(str(HERE / "bind-selected-package-receipts.py"))["acquisition"]
entry["acquisition"] = acquisition(read(HERE / entry["construction"]))
physical = HERE / "update035-rail-at-physical-preparation/proof.json"
entry["physical_preparation"] = {"receipt": str(physical.relative_to(HERE)), "sha256": sha(physical)}
acceptance = dict(template["delivery_acceptance"])
acceptance["case_id"] = entry["case_id"]
auditor = HERE / "probe-seven-case-delivery-audit.py"
acceptance["script"] = auditor.name
acceptance["script_sha256"] = sha(auditor)
for name in ("command", "negative_command"):
    acceptance[name] = acceptance[name].replace(template["case_id"], entry["case_id"])
for name, stem in (("test", "positive"), ("negative", "negative")):
    log = HERE / ("update035-rail-at-delivery-" + stem + ".log")
    acceptance[name + "_log"] = str(log.relative_to(HERE))
    acceptance[name + "_log_sha256"] = sha(log)
entry["delivery_acceptance"] = acceptance
for case in manifest["cases"]:
    validate_candidates(HERE, case, "NRS-484B-213-2b", "C110454",
                        required=True, require_alternate=True, candidate_count=4)
    validate_case(HERE, case, ["full-train"])
    validate_physical(ROOT, HERE, case)
check_receipts(ROOT, HERE, manifest)
target = HERE / "update035-seven-case-bound-probe-manifest.json"
target.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"cases": 7, "candidates": 28, "bound_probe_sha256": sha(target),
                  "canonical_selected": False, "original_native_accepted": False}))
