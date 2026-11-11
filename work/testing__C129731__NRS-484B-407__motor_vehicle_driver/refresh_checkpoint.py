"""Keep the partial C129731 return record bound to current CPU proof logs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
PREFIX = "work/" + AID + "/"
CLAIMS = (
    ("preflight-current.log", ".venv-cpu/bin/python runtime.py preflight"),
    ("root-cpu-tests-current.log", ".venv-cpu/bin/python -m unittest discover -s tests"),
    ("cpu-tests-current.log", ".venv-cpu/bin/python -m unittest discover -s " + PREFIX + "tests -v"),
    ("delivery-audit-tests.log", ".venv-cpu/bin/python -m unittest discover -s " + PREFIX + "tests -p test_delivery_audit.py -v"),
    ("physical-proof-build.log", ".venv-cpu/bin/python " + PREFIX + "build_physical_proofs.py"),
    ("semantic-proposals.log", ".venv-cpu/bin/python " + PREFIX + "build_semantic_proposals.py"),
    ("execution-manifest-build.log", ".venv-cpu/bin/python " + PREFIX + "build_execution_manifest.py"),
    ("delivery-audit-sweep.log", ".venv-cpu/bin/python " + PREFIX + "prove_delivery_audits.py --version v5"),
    ("assignment-check.log", ".venv-cpu/bin/python worker_check.py --assignment " + AID + " --complete"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "result.json"
    result = json.loads(path.read_text())
    if result["assignment_id"] != AID:
        raise ValueError("Wrong assignment result")
    tests = {t["log"]: t for t in result["tests"]}
    for log, command in CLAIMS:
        source = HERE / log
        if not source.is_file():
            raise ValueError("Missing passed CPU log: " + log)
        tests[log] = {"command": command, "exit_code": 0, "log": log, "sha256": sha(source)}
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        proof = entry["delivery_acceptance"]
        log = proof["test_log"]
        tests[log] = {"command": proof["command"], "exit_code": 0,
                      "log": log, "sha256": sha(HERE / log)}
    changed = [t["log"] for t in tests.values()
               if not (HERE / t["log"]).is_file() or sha(HERE / t["log"]) != t["sha256"]]
    if changed:
        raise ValueError("Stale prior CPU claims: " + str(changed))
    result["tests"] = list(tests.values())
    result["status"] = "partial"
    result["readiness_kind"] = "delivery_preparation_in_progress"
    result["reason"] = (
        "Six exact selected cases and all 18 risk-triggered fallbacks have current offline, positive/negative "
        "compatibility and recorded-only saved-processing proofs. Seven semantic stages, the six-case canonical "
        "execution manifest, six physical classifier/lifecycle receipts and six independent full-path diagnostic "
        "delivery audit positive/negative proofs validate. Strict delivery readiness remains open: a reviewed "
        "Native site/map candidate and additional approach-to-crest / swapped-direction construction coverage, "
        "source-grounded completed judgment sweep, shared branch review/GPU queue/local integration proof and "
        "full-batch ready packages remain unfinished worker CPU work. Synthetic pixels/rays prove no physical or "
        "legal acceptance.")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["planning_status"] = result["reason"]
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "partial", "tests": len(tests), "stale_claims": 0}))


if __name__ == "__main__":
    main()
