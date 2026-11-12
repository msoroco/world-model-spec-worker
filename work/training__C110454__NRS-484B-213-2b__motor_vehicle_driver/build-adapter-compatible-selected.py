"""Clone selected exact bundles with only supported Core atom requirements.

Railroad and one-way facts remain mandatory Native statutory-context sources and
measurement-contract checks. They are not represented by unsupported Core atoms.
"""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "runtime/pipeline"),
                str(ROOT / "runtime/pipeline/scenario_pipeline")]
from scenario_pipeline.worker_exchange.preparation import runtime_for
from scenario_pipeline.worker_exchange.runtime_cli import verify
from scenario_pipeline.worker_exchange.atom_preflight import check_required_atoms


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = HERE / "execution-manifest.json"
manifest = json.loads(source.read_text())
assert len(manifest["cases"]) == 7
runtime = runtime_for(ROOT, json.loads((ROOT / "batch.json").read_text()))
verify(runtime)
probe = deepcopy(manifest)
probe["status"] = "partial_adapter_compatible_candidate_probe"
rows = []
for entry in probe["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    unsupported = "st.railway_crossing" if suffix.startswith("rail_") else (
        "st.one_way_roadway" if suffix.startswith("oneway_") else None)
    for candidate in (entry, *entry["candidates"]):
        ident = candidate["id"]
        old_path = HERE / candidate["construction"]
        original = json.loads(old_path.read_text())
        if unsupported is None:
            continue
        clone = deepcopy(original)
        config_file = next(f for f in clone["files"] if f["path"] == "config.json")
        config = json.loads(config_file["content"])
        atoms = config["required_atoms"]
        assert atoms.count(unsupported) == 1
        atoms.remove(unsupported)
        assert "statutory_context.json" in config.get("mandatory_original_sources", []) or (
            any(f["path"] == "statutory_context.py" for f in clone["files"]))
        check_required_atoms(runtime, atoms, config.get("source_packets", []), config)
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        target = HERE / "update037-adapter-candidates" / suffix / ident / "construction.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(clone, indent=2) + "\n")
        candidate["construction"] = str(target.relative_to(HERE))
        candidate["construction_sha256"] = sha(target)
        candidate.pop("offline", None)
        candidate.pop("compatibility", None)
        rows.append({"case_id": entry["case_id"], "candidate_id": ident,
                     "removed_unsupported_core_atom": unsupported,
                     "construction": candidate["construction"],
                     "construction_sha256": candidate["construction_sha256"]})
    if unsupported is not None:
        for name in ("negative", "post_capture", "physical_preparation", "delivery_acceptance"):
            entry.pop(name, None)
        entry["preparation_status"] = "adapter_compatible_bundle_proofs_pending"
        entry["acquisition"] = {}
assert len(rows) == 20
path = HERE / "update037-adapter-probe-manifest.json"
path.write_text(json.dumps(probe, indent=2) + "\n")
index = {"format": "c110454-adapter-compatible-candidate-clones-v1",
         "source_manifest_sha256": sha(source), "probe_manifest_sha256": sha(path),
         "revised_candidates": rows, "original_native_accepted": False}
out = HERE / "update037-adapter-candidate-index.json"
out.write_text(json.dumps(index, indent=2) + "\n")
print(json.dumps({"revised_candidates": len(rows),
                  "probe_manifest_sha256": sha(path), "index_sha256": sha(out)}))
