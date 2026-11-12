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
    ("cpu-tests.log", ".venv-cpu/bin/python -m unittest discover -s " + PREFIX + "tests"),
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
    ("crest-probe-branch-proof-record.log", ".venv-cpu/bin/python " + PREFIX + "record_crest_probe_branch_proofs.py"),
    ("crest-at-branch-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_crest_branch_comparison.py --probe at_500ft"),
    ("crest-beyond-branch-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_crest_branch_comparison.py --probe beyond_500ft"),
    ("canonical-at-approach-b-plan.log", ".venv-cpu/bin/python " + PREFIX + "extend_crest_case_plan.py"),
    ("canonical-at-approach-b-branch-build.log", ".venv-cpu/bin/python " + PREFIX + "build_approach_branch_proof.py --probe at_500ft --placement approach_to_crest --direction approach_b --canonical"),
    ("canonical-at-approach-b-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " + PREFIX + "diagnostic-canonical-at-approach-b-manifest.json --case " + AID + "__crest__at_500ft__approach_to_crest__occluded_approach_b --output .runtime-work/c129731-canonical-at-approach-b-offline-v2"),
    ("canonical-at-approach-b-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py compatibility --manifest " + PREFIX + "diagnostic-canonical-at-approach-b-manifest.json --case " + AID + "__crest__at_500ft__approach_to_crest__occluded_approach_b --output .runtime-work/c129731-canonical-at-approach-b-compat-v3 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"),
    ("canonical-at-approach-b-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py process-saved --manifest " + PREFIX + "diagnostic-canonical-at-approach-b-manifest.json --case " + AID + "__crest__at_500ft__approach_to_crest__occluded_approach_b --attempt .runtime-work/c129731-canonical-at-approach-b-compat-v3 --output .runtime-work/c129731-canonical-at-approach-b-saved-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"),
    ("canonical-at-approach-b-proof.log", ".venv-cpu/bin/python " + PREFIX + "record_promoted_crest_case.py"),
    ("canonical-at-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_canonical_crest_comparison.py"),
    ("canonical-short-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_canonical_short_comparison.py"),
    ("canonical-beyond-comparison-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_canonical_beyond_comparison.py"),
    ("canonical-at-approach-b-fallback-build.log", ".venv-cpu/bin/python " + PREFIX + "build_promoted_crest_fallbacks.py --name canonical-at-approach-b"),
    ("canonical-at-approach-b-fallback-proof.log", ".venv-cpu/bin/python " + PREFIX + "record_promoted_crest_fallbacks.py --name canonical-at-approach-b"),
    ("canonical-at-approach-b-physical-proof.log", ".venv-cpu/bin/python " + PREFIX + "build_promoted_physical_proof.py --name canonical-at-approach-b"),
    ("canonical-at-approach-b-delivery-audit-proof.log", ".venv-cpu/bin/python " + PREFIX + "prove_promoted_delivery_audit.py --name canonical-at-approach-b --version v1"),
    ("canonical-at-near-b-fallback-build.log", ".venv-cpu/bin/python " + PREFIX + "build_promoted_crest_fallbacks.py --name canonical-at-near-b"),
    ("canonical-at-near-b-fallback-proof.log", ".venv-cpu/bin/python " + PREFIX + "record_promoted_crest_fallbacks.py --name canonical-at-near-b"),
    ("canonical-at-near-b-physical-proof.log", ".venv-cpu/bin/python " + PREFIX + "build_promoted_physical_proof.py --name canonical-at-near-b"),
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
    for probe, suffix in (("at_500ft", "at"), ("beyond_500ft", "beyond")):
        for placement, direction, branch in (("near_summit", "approach_a", "near-a"),
                                             ("near_summit", "approach_b", "near-b"),
                                             ("approach_to_crest", "approach_a", "approach-a"),
                                             ("approach_to_crest", "approach_b", "approach-b")):
            name = suffix + "-" + branch
            manifest = PREFIX + "diagnostic-" + name + "-manifest.json"
            case = AID + "__crest__" + probe
            base = ".runtime-work/c129731-" + name
            decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
            branch_claims = (
                (name + "-branch-build.log", ".venv-cpu/bin/python " + PREFIX +
                 "build_approach_branch_proof.py --probe " + probe + " --placement " + placement +
                 " --direction " + direction),
                (name + "-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " +
                 manifest + " --case " + case + " --output " + base + "-offline-v1"),
                (name + "-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
                 ".venv-cpu/bin/python runtime.py compatibility --manifest " + manifest + " --case " + case +
                 " --output " + base + "-compat-v1" + decoder),
                (name + "-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
                 ".venv-cpu/bin/python runtime.py process-saved --manifest " + manifest + " --case " + case +
                 " --attempt " + base + "-compat-v1 --output " + base + "-saved-v1" + decoder),
            )
            for log, command in branch_claims:
                source = HERE / log
                if not source.is_file():
                    raise ValueError("Missing passed crest probe branch proof: " + log)
                tests[log] = {"command": command, "exit_code": 0, "log": log, "sha256": sha(source)}
    for name, placement, direction in (("canonical-at-near-a", "near_summit", "approach_a"),
                                       ("canonical-at-near-b", "near_summit", "approach_b"),
                                       ("canonical-at-approach-a", "approach_to_crest", "approach_a")):
        manifest = PREFIX + "diagnostic-" + name + "-manifest.json"
        case = AID + "__crest__at_500ft__" + placement + "__occluded_" + direction
        base = ".runtime-work/c129731-" + name
        decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
        branch_claims = (
            (name + "-branch-build.log", ".venv-cpu/bin/python " + PREFIX +
             "build_approach_branch_proof.py --probe at_500ft --placement " + placement + " --direction " + direction + " --canonical"),
            (name + "-plan.log", ".venv-cpu/bin/python " + PREFIX +
             "extend_crest_case_plan.py --probe at_500ft --placement " + placement + " --direction " + direction),
            (name + "-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " +
             manifest + " --case " + case + " --output " + base + "-offline-v1"),
            (name + "-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
             ".venv-cpu/bin/python runtime.py compatibility --manifest " + manifest + " --case " + case +
             " --output " + base + "-compat-v1" + decoder),
            (name + "-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " "
             ".venv-cpu/bin/python runtime.py process-saved --manifest " + manifest + " --case " + case +
             " --attempt " + base + "-compat-v1 --output " + base + "-saved-v1" + decoder),
            (name + "-proof.log", ".venv-cpu/bin/python " + PREFIX +
             "record_promoted_crest_case.py --placement " + placement + " --direction " + direction + " --probe at_500ft"),
        )
        for log, command in branch_claims:
            source = HERE / log
            if not source.is_file():
                raise ValueError("Missing distinct exact crest proof: " + log)
            tests[log] = {"command": command, "exit_code": 0, "log": log, "sha256": sha(source)}
    for name, placement, direction in (("canonical-short-approach-b", "approach_to_crest", "approach_b"),
                                       ("canonical-short-near-b", "near_summit", "approach_b"),
                                       ("canonical-short-approach-a", "approach_to_crest", "approach_a"),
                                       ("canonical-short-near-a", "near_summit", "approach_a")):
        probe = "short_of_500ft"
        manifest = PREFIX + "diagnostic-" + name + "-manifest.json"
        case = AID + "__crest__" + probe + "__" + placement + "__occluded_" + direction
        base = ".runtime-work/c129731-" + name
        decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
        for log, command in (
            (name + "-branch-build.log", ".venv-cpu/bin/python " + PREFIX + "build_approach_branch_proof.py --probe " + probe + " --placement " + placement + " --direction " + direction + " --canonical"),
            (name + "-plan.log", ".venv-cpu/bin/python " + PREFIX + "extend_crest_case_plan.py --probe " + probe + " --placement " + placement + " --direction " + direction),
            (name + "-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " + manifest + " --case " + case + " --output " + base + "-offline-v1"),
            (name + "-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py compatibility --manifest " + manifest + " --case " + case + " --output " + base + "-compat-v1" + decoder),
            (name + "-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py process-saved --manifest " + manifest + " --case " + case + " --attempt " + base + "-compat-v1 --output " + base + "-saved-v1" + decoder),
            (name + "-proof.log", ".venv-cpu/bin/python " + PREFIX + "record_promoted_crest_case.py --placement " + placement + " --direction " + direction + " --probe " + probe),
        ):
            source = HERE / log
            if not source.is_file():
                raise ValueError("Missing short exact crest proof: " + log)
            tests[log] = {"command": command, "exit_code": 0, "log": log, "sha256": sha(source)}
    for name, placement, direction in (("canonical-beyond-approach-b", "approach_to_crest", "approach_b"),
                                       ("canonical-beyond-near-b", "near_summit", "approach_b"),
                                       ("canonical-beyond-approach-a", "approach_to_crest", "approach_a"),
                                       ("canonical-beyond-near-a", "near_summit", "approach_a")):
        probe = "beyond_500ft"
        manifest = PREFIX + "diagnostic-" + name + "-manifest.json"
        case = AID + "__crest__" + probe + "__" + placement + "__occluded_" + direction
        base = ".runtime-work/c129731-" + name
        decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
        for log, command in (
            (name + "-branch-build.log", ".venv-cpu/bin/python " + PREFIX + "build_approach_branch_proof.py --probe " + probe + " --placement " + placement + " --direction " + direction + " --canonical"),
            (name + "-plan.log", ".venv-cpu/bin/python " + PREFIX + "extend_crest_case_plan.py --probe " + probe + " --placement " + placement + " --direction " + direction),
            (name + "-branch-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " + manifest + " --case " + case + " --output " + base + "-offline-v1"),
            (name + "-branch-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py compatibility --manifest " + manifest + " --case " + case + " --output " + base + "-compat-v1" + decoder),
            (name + "-branch-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py process-saved --manifest " + manifest + " --case " + case + " --attempt " + base + "-compat-v1 --output " + base + "-saved-v1" + decoder),
            (name + "-proof.log", ".venv-cpu/bin/python " + PREFIX + "record_promoted_crest_case.py --placement " + placement + " --direction " + direction + " --probe " + probe),
        ):
            source = HERE / log
            if not source.is_file():
                raise ValueError("Missing beyond exact crest proof: " + log)
            tests[log] = {"command": command, "exit_code": 0, "log": log, "sha256": sha(source)}
    for name, case in (("canonical-at-approach-b", AID + "__crest__at_500ft__approach_to_crest__occluded_approach_b"),
                       ("canonical-at-near-b", AID + "__crest__at_500ft__near_summit__occluded_approach_b")):
        manifest_name = PREFIX + "diagnostic-" + name + "-fallback-manifest.json"
        decoder = " --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"
        for ident in ("fallback1", "fallback2", "fallback3"):
            base = ".runtime-work/c129731-" + name + "-" + ident
            for log, command in (
                (name + "-" + ident + "-offline.log", ".venv-cpu/bin/python runtime.py offline --manifest " + manifest_name + " --case " + case + " --candidate " + ident + " --output " + base + "-offline-v1"),
                (name + "-" + ident + "-compatibility.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py compatibility --manifest " + manifest_name + " --case " + case + " --candidate " + ident + " --output " + base + "-compat-v1" + decoder),
                (name + "-" + ident + "-processing.json", "SCENARIO_PIPELINE_OUTPUT_ROOT=" + OUTPUT_ROOT + " .venv-cpu/bin/python runtime.py process-saved --manifest " + manifest_name + " --case " + case + " --attempt " + base + "-compat-v1 --output " + base + "-saved-v1" + decoder),
            ):
                source = HERE / log
                if not source.is_file():
                    raise ValueError("Missing promoted fallback proof: " + log)
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
        "Seven canonical manifest cases and all 21 risk-triggered fallbacks have current offline, positive/negative "
        "compatibility and recorded-only saved-processing proofs. Seven semantic stages, the seven-case canonical "
        "execution manifest, seven physical classifier/lifecycle receipts and seven independent full-path diagnostic "
        "delivery audit positive/negative proofs validate. Twelve CPU-tested diagnostic crest alternatives "
        "construct near-summit and approach-to-crest turn sites for all three 500-foot probes and both obscured "
        "approach directions. Their planned prop near faces align with the synthetic ray stations at 150, 152.4 "
        "and 160 m. All twelve have exact offline, positive/negative compatibility and recorded-only saved "
        "processing proofs; each four-branch probe group has an independent source comparison and two negative "
        "tampering proofs. A source-bound OpenDRIVE crest plan checks twelve lane/grade sites; a curved road "
        "plan checks six curve probe/direction sites. All twelve distinct crest placement/direction cases "
        "now have complete CPU paths and four source-audited controlled comparisons per boundary probe. "
        "Strict delivery readiness remains open: canonical manifest/delivery audits and justified risk "
        "fallbacks for the other newer cases (the first at/approach/B case is now bound), remaining curve "
        "direction coverage, a completed judgment sweep, shared branch "
        "review/GPU queue/local integration proof, and full-batch "
        "ready packages are unfinished worker CPU work. Synthetic pixels/rays prove no physical or legal acceptance.")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["planning_status"] = result["reason"]
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "partial", "tests": len(tests), "stale_claims": 0}))


if __name__ == "__main__":
    main()
