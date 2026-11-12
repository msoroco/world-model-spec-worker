"""CPU proof of exact C104538 queue intent and current CLI shapes."""
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
SPEC = importlib.util.spec_from_file_location("queue_builder", HERE / "build-queue-fragment.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(fragment):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    require(fragment["status"] == "partial" and fragment["dispatchable"] is False,
            "Fragment must not dispatch")
    require(fragment["manifest_sha256"] == MODULE.sha(HERE / "execution-manifest.json") and
            fragment["case_plan_sha256"] == MODULE.sha(HERE / "case-plan.json"), "Stale source hashes")
    expected = [entry["case_id"] for entry in manifest["cases"]]
    rows = fragment["cases"]
    require([row["case_id"] for row in rows] == expected and
            [row["order"] for row in rows] == [1, 2, 3], "Exact case coverage/order changed")
    for row, entry in zip(rows, manifest["cases"]):
        case = row["case_id"]
        require(row["assignment_id"] == MODULE.AID and row["status"] == "partial" and
                row["dispatchable"] is False, "Case row promoted")
        require(set(row["candidate_commands"]) == {c["id"] for c in entry["candidates"]},
                "Fallback coverage changed")
        for key in ("capture_command", "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command", "prepare_command", "execute_command", "accept_command"):
            tokens = shlex.split(row[key])
            require(case in row[key] and tokens, "Missing exact case in " + key)
        for candidate, cmd in row["candidate_commands"].items():
            require(candidate in shlex.split(cmd) and case in shlex.split(cmd), "Fallback command changed")
        require("--candidate primary" in row["capture_command"] and
                "--candidate primary" in row["prepare_command"], "Primary selection changed")
        require("--owner-release-receipt" in row["postprocessing_command"],
                "Saved processing missing owner-release receipt")
    comparisons = fragment["comparison_audit_commands"]
    require(len(comparisons) == 1 and comparisons[0]["comparison_id"] == plan["comparisons"][0]["comparison_id"] and
            comparisons[0]["case_ids"] == plan["comparisons"][0]["case_ids"] and
            comparisons[0]["dispatchable"] is False, "Comparison identity changed")
    require(comparisons[0]["command"].count("--attempt") == 3 and
            comparisons[0]["command"].count("--saved") == 3, "Comparison sources incomplete")


def cli_help(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "runtime/pipeline/scenario_pipeline")
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=True, env=env)
    return result.stdout


def main():
    fragment = MODULE.build()
    check(fragment)
    artifact = HERE / "update024-selected-queue-fragment.json"
    require(json.loads(artifact.read_text()) == fragment, "Retained queue fragment changed")
    py = str(ROOT / ".venv-cpu/bin/python")
    runtime_help = {name: cli_help(py, "runtime.py", name, "--help")
                    for name in ("capture", "process-saved", "owner-released")}
    exchange_help = {name: cli_help(py, "-m", "worker_exchange", name, "--help")
                     for name in ("prepare-delivery", "execute-delivery", "accept-delivery")}
    # worker_exchange is found via PYTHONPATH on the actual queue command; the
    # proof subprocess receives the same module path without invoking dispatch.
    for key, flags in {"capture": ("--candidate", "--manifest", "--case"),
                       "process-saved": ("--owner-release-receipt", "--case"),
                       "owner-released": ("--acknowledge-owner-released",)}.items():
        require(all(flag in runtime_help[key] for flag in flags), "Runtime CLI changed: " + key)
    for key, flags in {"prepare-delivery": ("--candidate", "--case"),
                       "execute-delivery": ("--run", "--job", "--case"),
                       "accept-delivery": ("--attempt", "--audit", "--case")}.items():
        require(all(flag in exchange_help[key] for flag in flags), "Exchange CLI changed: " + key)
    source_help = cli_help(py, str(HERE / "delivery_audit.py"), "--help")
    comparison_help = cli_help(py, str(HERE / "comparison_audit.py"), "--help")
    require(all(flag in source_help for flag in ("--case", "--candidate", "--decode-dir", "--output")),
            "Delivery audit CLI changed")
    require("--attempt" in comparison_help and "--saved" in comparison_help,
            "Comparison audit CLI changed")
    rejected = []
    for name, mutate in (
        ("missing_case", lambda f: f["cases"].pop()),
        ("missing_fallback", lambda f: f["cases"][0]["candidate_commands"].pop("fallback3")),
        ("false_dispatch", lambda f: f.update(dispatchable=True)),
        ("stale_manifest", lambda f: f.update(manifest_sha256="0" * 64)),
        ("missing_comparison_source", lambda f: f["comparison_audit_commands"][0].update(command="--attempt x --saved y")),
    ):
        damaged = copy.deepcopy(fragment)
        mutate(damaged)
        try:
            check(damaged)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Mutation accepted: " + name)
    result = {"format": "c104538-queue-fragment-cpu-proof-v1", "cases": len(fragment["cases"]),
              "fallbacks": sum(len(row["candidate_commands"]) for row in fragment["cases"]),
              "comparisons": len(fragment["comparison_audit_commands"]),
              "cli_help_checked": 8, "mutations_rejected": rejected,
              "fragment_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
              "dispatchable": False, "physical_or_local_acceptance_claimed": False}
    (HERE / "update024-queue-fragment-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
