"""Bind acquisition and saved-only CPU evidence to selected cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


m = json.loads(MANIFEST.read_text())
for entry in m["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    proof = ROOT / "proofs" / suffix
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    required = set(config["required_atoms"]) | {c["name"] for c in construction["recording_description"]["channels"]}
    entry["acquisition"] = {atom: {"entrypoint": "runner.py" if atom in config["required_atoms"] else "finalize.py",
                                    "method": "Original Native frame and body join with separate surveyed property, signal, and controller-purpose source",
                                    "evidence": "Synthetic public fixture verifies source processing; independent Native capture remains required"}
                            for atom in sorted(required)}
    saved = proof / "saved-proof.json"
    processing = proof / "processing.json"
    log = proof / "saved-analysis.log"
    entry["saved_cpu_proof"] = {"receipt": str(saved.relative_to(ROOT)), "sha256": sha(saved),
                                "processing": str(processing.relative_to(ROOT)), "processing_sha256": sha(processing),
                                "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)}
    entry["post_capture"] = {"recorded_only": True,
                             "command": f"$CARLA_PYTHON runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {entry['case_id']} --attempt \"$SAVED_ATTEMPT\" --output \"$PROCESSED_OUT\" --library runtime/library --validator $CORE_VALIDATOR",
                             "feedback_command": "cat \"$PROCESSED_OUT/v0001/feedback.json\"",
                             "test_exit_code": 0, "test_log": str(log.relative_to(ROOT)), "test_log_sha256": sha(log)}
m["status"] = "partial_cpu_chain_bound"
MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
print(sha(MANIFEST))
