"""Keep the partial C129731 return record bound to current CPU proof logs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
PREFIX = "work/" + AID + "/"
OUTPUT_ROOT = str(ROOT / ".runtime-work/pipeline-output")
CLAIMS = (
    ("preflight-current.log", ".venv-cpu/bin/python runtime.py preflight"),
    ("root-cpu-tests-current.log", ".venv-cpu/bin/python -m unittest discover -s tests"),
    ("cpu-tests-current.log", ".venv-cpu/bin/python -m unittest discover -s " + PREFIX + "tests -v"),
    ("delivery-audit-tests.log", ".venv-cpu/bin/python -m unittest discover -s " + PREFIX + "tests -p test_delivery_audit.py -v"),
    ("physical-proof-build.log", ".venv-cpu/bin/python " + PREFIX + "build_physical_proofs.py"),
    ("semantic-proposals.log", ".venv-cpu/bin/python " + PREFIX + "build_semantic_proposals.py"),
    ("execution-manifest-build.log", ".venv-cpu/bin/python " + PREFIX + "build_execution_manifest.py"),
    ("delivery-audit-sweep.log", ".venv-cpu/bin/python " + PREFIX + "prove_delivery_audits.py --version v5"),
    ("branch-site-build.log", ".venv-cpu/bin/python " + PREFIX + "build_branch_sites.py"),
    ("crest-opendrive-build.log", ".venv-cpu/bin/python " + PREFIX + "build_crest_opendrive.py"),
    ("curve-opendrive-build.log", ".venv-cpu/bin/python " + PREFIX + "build_curve_opendrive.py"),
    ("approach-branch-build.log", ".venv-cpu/bin/python " + PREFIX + "build_approach_branch_proof.py"),
    ("approach-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " + PREFIX + "diagnostic-approach-b-manifest.json --case " + AID + "__crest__short_of_500ft --output .runtime-work/c129731-approach-b-offline-v4"),
    ("approach-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py compatibility --manifest " + PREFIX + "diagnostic-approach-b-manifest.json --case " + AID + "__crest__short_of_500ft --output .runtime-work/c129731-approach-b-compat-v5 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"),
    ("approach-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py process-saved --manifest " + PREFIX + "diagnostic-approach-b-manifest.json --case " + AID + "__crest__short_of_500ft --attempt .runtime-work/c129731-approach-b-compat-v5 --output .runtime-work/c129731-approach-b-saved-v2 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"),
    ("crest-branch-proof-record.log", ".venv-cpu/bin/python " + PREFIX + "record_crest_branch_proofs.py"),
    ("crest-branch-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_crest_branch_comparison.py"),
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
    for name, placement, direction in (("near-a", "near_summit", "approach_a"),
                                       ("near-b", "near_summit", "approach_b"),
                                       ("approach-a", "approach_to_crest", "approach_a")):
        manifest = PREFIX + "diagnostic-" + name + "-manifest.json"
        case = AID + "__crest__short_of_500ft"
        base = ".runtime-work/c129731-" + name
        decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
        branch_claims = (
            (name + "-branch-build.log", ".venv-cpu/bin/python " + PREFIX +
             "build_approach_branch_proof.py --placement " + placement + " --direction " + direction),
            (name + "-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " +
             manifest + " --case " + case + " --output " + base + "-offline-v2"),
            (name + "-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
             ".venv-cpu/bin/python runtime.py compatibility --manifest " + manifest + " --case " + case +
             " --output " + base + "-compat-v2" + decoder),
            (name + "-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
             ".venv-cpu/bin/python runtime.py process-saved --manifest " + manifest + " --case " + case +
             " --attempt " + base + "-compat-v2 --output " + base + "-saved-v2" + decoder),
        )
        for log, command in branch_claims:
            source = HERE / log
            if not source.is_file():
                raise ValueError("Missing passed crest branch proof: " + log)
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
        "delivery audit positive/negative proofs validate. Four CPU-tested diagnostic crest alternatives now "
        "construct near-summit and approach-to-crest turn sites with either approach ray occluded; a separate "
        "source-bound OpenDRIVE crest road plan verifies lane stations and grade geometry; a separate curved "
        "OpenDRIVE road plan verifies six source-bound curve probe/direction site packets. Strict delivery "
        "readiness remains open: actual CARLA ingestion and Native asset/site review (a guarded loader has CPU "
        "mock proofs), full positive/negative saved "
        "processing proofs for the other new alternatives (all four short-probe crest placement/direction "
        "branches now have full diagnostic offline, compatibility and recorded-only saved proofs), a "
        "independent four-alternative source comparison passed its software checks and two negative tampering "
        "proofs; a completed source-grounded judgment "
        "sweep, shared branch review/GPU queue/local integration proof and "
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
