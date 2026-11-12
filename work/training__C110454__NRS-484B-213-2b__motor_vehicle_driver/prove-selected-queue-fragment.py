"""Check current selected queue intent and reject false dispatch promotion."""
import copy
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("c110454_queue", HERE / "build-selected-queue-fragment.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(fragment):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    require(fragment.get("format") == "c110454-selected-queue-fragment-v1" and
            fragment.get("status") == "partial" and fragment.get("dispatchable") is False,
            "Queue fragment must remain partial")
    require(fragment.get("manifest_sha256") == MODULE.sha(HERE / "execution-manifest.json") and
            fragment.get("case_plan_sha256") == MODULE.sha(HERE / "case-plan.json"),
            "Queue source hash changed")
    rows = fragment["cases"]
    require([row["case_id"] for row in rows] == [item["case_id"] for item in manifest["cases"]] and
            [row["order"] for row in rows] == list(range(1, 8)),
            "Selected case order or coverage changed")
    for row, entry in zip(rows, manifest["cases"]):
        case = entry["case_id"]
        require(row.get("assignment_id") == MODULE.AID and row.get("status") == "partial" and
                row.get("dispatchable") is False and
                row.get("construction_sha256") == entry["construction_sha256"],
                "Selected case identity or dispatch status changed")
        for key in ("capture_command", "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command", "prepare_command", "execute_command", "accept_command"):
            require(case in row[key], "Exact case absent from " + key)
        require(all(flag in shlex.split(row["additional_source_audit_command"]) for flag in
                    ("--pixel-review", "--context-review", "--primary-video", "--core-trace",
                     "--decode-receipt", "--job-id", "--attempt-number", "--recording-id")),
                "Original delivery audit inputs incomplete")
        require(set(row["candidate_commands"]) == {c["id"] for c in entry["candidates"]},
                "Fallback coverage changed")
        for candidate, cmd in row["candidate_commands"].items():
            require(case in shlex.split(cmd) and candidate in shlex.split(cmd),
                    "Fallback preparation identity changed")
        require("--owner-release-receipt" in shlex.split(row["postprocessing_command"]),
                "Saved processing lost owner release binding")
        require("original_postprocess_handoff.py" in row["postprocessing_command"],
                "Selected queue bypasses source-bound owner handoff")
        require(row["postprocessing_command"] == entry["post_capture"]["command"],
                "Selected queue and manifest post-capture commands differ")
    expected = [item for item in plan["comparisons"]
                if item["comparison_id"].removeprefix(MODULE.AID + "__comparison_") in MODULE.PAIRS]
    comparisons = fragment["comparison_audit_commands"]
    require(len(comparisons) == len(expected) == 4 and
            [(item["comparison_id"], item["case_ids"]) for item in comparisons] ==
            [(item["comparison_id"], item["case_ids"]) for item in expected],
            "Selected comparison coverage changed")
    for item in comparisons:
        tokens = shlex.split(item["command"])
        require(item["status"] == "partial" and item["dispatchable"] is False and
                all(flag in tokens for flag in ("--left-attempt", "--left-saved",
                                                 "--right-attempt", "--right-saved")),
                "Comparison sources or dispatch status changed")
    require(fragment["withheld_comparison_id"] == MODULE.AID + "__comparison_main",
            "Accepted-original comparison disposition changed")


def cli_help(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "runtime/pipeline/scenario_pipeline")
    return subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, check=True, env=env).stdout


def main():
    fragment = MODULE.build()
    check(fragment)
    artifact = HERE / "update020-selected-queue-fragment.json"
    require(json.loads(artifact.read_text()) == fragment, "Retained fragment differs")
    py = str(ROOT / ".venv-cpu/bin/python")
    runtime = {name: cli_help(py, "runtime.py", name, "--help")
               for name in ("capture", "process-saved", "owner-released")}
    exchange = {name: cli_help(py, "-m", "worker_exchange", name, "--help")
                for name in ("prepare-delivery", "execute-delivery", "accept-delivery")}
    for name, flags in {"capture": ("--candidate", "--manifest", "--case"),
                        "process-saved": ("--owner-release-receipt", "--case"),
                        "owner-released": ("--acknowledge-owner-released",)}.items():
        require(all(flag in runtime[name] for flag in flags), "Runtime CLI changed: " + name)
    for name, flags in {"prepare-delivery": ("--candidate", "--case"),
                        "execute-delivery": ("--run", "--job", "--case"),
                        "accept-delivery": ("--attempt", "--audit", "--case")}.items():
        require(all(flag in exchange[name] for flag in flags), "Exchange CLI changed: " + name)
    audit_help = cli_help(py, str(HERE / "delivery_audit.py"), "--help")
    require(all(flag in audit_help for flag in
                ("--pixel-review", "--context-review", "--primary-video", "--core-trace",
                 "--decode-receipt", "--job-id", "--attempt-number", "--recording-id")),
            "Delivery auditor CLI changed")
    handoff_help = cli_help(py, str(HERE / "original_postprocess_handoff.py"), "--help")
    require(all(flag in handoff_help for flag in
                ("--manifest", "--case", "--attempt", "--output", "--library",
                 "--validator", "--owner-release-receipt")),
            "Original postprocessing handoff CLI changed")
    rejected = []
    for name, mutation in (
        ("missing_case", lambda f: f["cases"].pop()),
        ("stale_manifest", lambda f: f.update(manifest_sha256="0" * 64)),
        ("wrong_construction", lambda f: f["cases"][0].update(construction_sha256="0" * 64)),
        ("missing_fallback", lambda f: f["cases"][0]["candidate_commands"].pop("fallback3")),
        ("false_dispatch", lambda f: f.update(dispatchable=True)),
        ("missing_comparison", lambda f: f["comparison_audit_commands"].pop()),
        ("missing_release", lambda f: f["cases"][0].update(postprocessing_command="echo " + f["cases"][0]["case_id"])),
    ):
        damaged = copy.deepcopy(fragment)
        mutation(damaged)
        try:
            check(damaged)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Mutation accepted: " + name)
    proof = {"format": "c110454-selected-queue-fragment-proof-v1",
             "cases": len(fragment["cases"]),
             "fallbacks": sum(len(row["candidate_commands"]) for row in fragment["cases"]),
             "comparisons": len(fragment["comparison_audit_commands"]),
             "cli_help_checked": 8, "mutations_rejected": rejected,
             "fragment_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
             "dispatchable": False, "physical_or_local_acceptance_claimed": False}
    (HERE / "update020-selected-queue-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
