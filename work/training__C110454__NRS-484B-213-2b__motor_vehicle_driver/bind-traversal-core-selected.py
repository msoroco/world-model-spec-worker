"""Bind corrected Core requirements to selected cases with retained CPU proofs."""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


canonical_path = HERE / "execution-manifest.json"
canonical = read(canonical_path)
probe = read(HERE / "update039-traversal-core-probe-manifest.json")
retained = read(HERE / "update039-traversal-core-retained-index.json")
assert retained["candidate_count"] == 8
assert retained["manifest_sha256"] == sha(HERE / "update039-traversal-core-probe-manifest.json")
rows = {(x["case_id"], x["candidate_id"]): x for x in retained["candidates"]}
acquisition = runpy.run_path(str(HERE / "bind-selected-package-receipts.py"))["acquisition"]
count = 0
for entry in canonical["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    if not suffix.startswith("traversal_"):
        continue
    new = next(x for x in probe["cases"] if x["case_id"] == entry["case_id"])
    for candidate, changed in zip((entry, *entry["candidates"]), (new, *new["candidates"])):
        ident = candidate["id"]
        row = rows[(entry["case_id"], ident)]
        assert row["construction_sha256"] == changed["construction_sha256"]
        candidate["construction"] = changed["construction"]
        candidate["construction_sha256"] = changed["construction_sha256"]
        base = HERE / "update039-traversal-core-proofs" / suffix / ident
        candidate["offline"] = {
            "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry['case_id']} --candidate {ident} --output ${{OFFLINE_DIR}} --python .venv-cpu/bin/python",
            "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
            "log": str((base / "offline.log").relative_to(HERE)),
            "log_sha256": sha(base / "offline.log")}
        files = row["files"]
        candidate["compatibility"] = {
            "receipt": files["compatibility.json"]["path"],
            "sha256": files["compatibility.json"]["sha256"],
            "log": files["compatibility-analysis.log"]["path"],
            "negative_log": files["negative-analysis.log"]["path"]}
    neg = rows[(entry["case_id"], "primary")]["files"]["negative-analysis.log"]
    entry["negative"] = {"log": neg["path"], "log_sha256": neg["sha256"]}
    saved = HERE / "update039-traversal-core-proofs" / suffix / "primary/process-saved.log"
    entry["post_capture"]["test_log"] = str(saved.relative_to(HERE))
    entry["post_capture"]["test_log_sha256"] = sha(saved)
    entry["acquisition"] = acquisition(read(HERE / entry["construction"]))
    physical = HERE / "update039-traversal-core-physical-preparation" / suffix / "proof.json"
    entry["physical_preparation"] = {"receipt": str(physical.relative_to(HERE)),
                                     "sha256": sha(physical)}
    entry["preparation_status"] = "selected_final_hash_proofs_pending"
    count += 1
assert count == 2
snapshot = HERE / "update039-pre-traversal-core-manifest.json"
assert not snapshot.exists()
snapshot.write_bytes(canonical_path.read_bytes())
canonical_path.write_text(json.dumps(canonical, indent=2) + "\n")
print(json.dumps({"changed_cases": count, "changed_candidates": 8,
                  "manifest_sha256": sha(canonical_path),
                  "delivery_audit_rebind_pending": True}))
