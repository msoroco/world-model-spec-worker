"""Build a bounded draft manifest for selected CPU compatibility proofs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def build():
    draft = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    batch = json.loads((REPO / "batch.json").read_text())
    result = {"format": "worker-execution-manifest",
              "assignment_id": ROOT.name,
              "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
              "cases": []}
    for case in draft["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[1]
        result["cases"].append({
            "case_id": case["case_id"], "kind": "delivery",
            "construction": case["construction"],
            "construction_sha256": case["construction_sha256"],
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "measurement_contract": "measurement-" + suffix + ".json",
            "fixture_recipe": "work/" + ROOT.name + "/fixture-recipe-" + suffix + ".json",
            "candidate_risk": case["candidate_risk"],
            "acquisition": {
                "intersection_body_history": {"entrypoint": "native_capture.py",
                    "method": "original synchronized Native body history",
                    "evidence": "native_trace.json"},
                "governing_signal_readback": {"entrypoint": "native_capture.py",
                    "method": "original Native governing signal readback",
                    "evidence": "native_trace.json"}},
        })
    (ROOT / "execution-manifest.compat-draft.json").write_text(
        json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    build()
