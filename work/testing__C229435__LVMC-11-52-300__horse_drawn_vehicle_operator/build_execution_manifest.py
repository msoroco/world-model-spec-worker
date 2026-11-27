"""Initialize exact selected construction bindings without claiming proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    prior_path = ROOT / "execution-manifest.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {"cases": []}
    old = {entry["case_id"]: entry for entry in prior["cases"]}
    plan = json.loads((ROOT / "case-plan.json").read_text())
    entries = []
    for case in plan["cases"]:
        ident = case["case_id"]
        suffix = ident.rsplit("__", 1)[-1]
        relative = "cases/" + suffix + "/construction.json"
        construction_sha256 = sha(ROOT / relative)
        entry = old.get(ident, {})
        if entry.get("construction_sha256") != construction_sha256:
            entry = {}
        entry.update({"case_id": ident, "kind": "delivery",
                      "construction": relative,
                      "construction_sha256": construction_sha256,
                      "candidate_risk": {
                          "status": "physical",
                          "reason": "Thirty-minute 20 Hz four-view capture risks dropped original frames or incomplete media closure."},
                      "candidates": entry.get("candidates", []),
                      "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
                      "measurement_procedure": {"entrypoint": "analysis.py"},
                      "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                         "host_env_var": "CARLA_HOST",
                                         "port_env_var": "CARLA_PORT"}})
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    prior_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
