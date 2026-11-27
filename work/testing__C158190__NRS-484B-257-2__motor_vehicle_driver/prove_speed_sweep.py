"""Bind CPU diagnostic proofs for the three staged speed cases."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import prove_compatibility

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "speed-sweep-manifest.draft.json"
SCRATCH = REPO / ".runtime-work/c158190-2572-final"
PYTHON = REPO / ".venv-cpu/bin/python"
DECODER = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: list[str], log: Path | None = None) -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    process = subprocess.run([str(PYTHON), str(REPO / "runtime.py"), *map(str, args)],
                             cwd=REPO, env=env, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    if log is not None:
        log.write_text(process.stdout.rstrip() + "\n")
    if process.returncode:
        raise ValueError("runtime proof failed: " + shlex.join(map(str, args)) +
                         "\n" + process.stdout[-1800:])


def save(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if not DECODER.is_file():
        raise ValueError("pinned Lean decoder unavailable")
    (SCRATCH / "tmp").mkdir(parents=True, exist_ok=True)
    (SCRATCH / "output").mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    prove_compatibility.MANIFEST = MANIFEST
    prove_compatibility.SCRATCH = SCRATCH
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1"):
            output = SCRATCH / ("speed-offline-" + suffix + "-" + candidate + "-v1")
            args = ["offline", "--manifest", str(MANIFEST), "--case", entry["case_id"],
                    "--output", str(output), "--python", str(PYTHON),
                    "--candidate", candidate]
            run(args)
            log = HERE / ("cpu-offline-" + suffix + "-" + candidate + ".log")
            log.write_text((output / "offline.log").read_text().rstrip() + "\n")
            receipt = {"command": shlex.join([str(PYTHON), str(REPO / "runtime.py"), *args]),
                       "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                       "construction_sha256": entry["construction_sha256"] if candidate == "primary"
                       else entry["candidates"][0]["construction_sha256"]}
            if candidate == "primary":
                entry["offline"] = receipt
            else:
                entry["candidates"][0]["offline"] = receipt
            print("offline:", suffix, candidate, flush=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
        entry["compatibility"] = prove_compatibility.run(entry, "primary", suffix, env)
        entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
        construction = json.loads((HERE / entry["construction"]).read_text())
        entry["acquisition"] = {channel["name"]: {
            "entrypoint": "analysis.py", "method": "saved_original_channel",
            "evidence": "channels/" + channel["name"] + ".jsonl"}
            for channel in construction["recording_description"]["channels"]}
        entry["acquisition"]["reviewed_nonthrough_stop_site_packet"] = {
            "entrypoint": "analysis.py", "method": "source-sealed original site packet",
            "evidence": "channels/context.json"}
        entry["candidates"][0]["compatibility"] = prove_compatibility.run(
            entry, "fallback1", suffix, env)
        print("compatibility:", suffix, flush=True)
        save(manifest)

    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        source = SCRATCH / ("speed-saved-source-" + suffix + "-v1")
        fixture = SCRATCH / ("speed-saved-fixture-" + suffix + "-v1")
        output = SCRATCH / ("speed-saved-proof-" + suffix + "-v1")
        run(["materialize", "--manifest", str(MANIFEST), "--case", entry["case_id"],
             "--output", str(source)])
        run(["fixture", "--recipe", str(REPO / entry["fixture_recipe"]),
             "--output", str(fixture)])
        for path in fixture.iterdir():
            destination = source / path.name
            if destination.exists():
                raise ValueError("fixture shadows construction: " + path.name)
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
        run(["process-saved", "--manifest", str(MANIFEST), "--case", entry["case_id"],
             "--attempt", str(source), "--output", str(output), "--library",
             str(REPO / "runtime/library"), "--validator", str(DECODER)])
        saved = HERE / ("cpu-saved-" + suffix + ".json")
        shutil.copyfile(output / "v0001/processing.json", saved)
        proof = json.loads(saved.read_text())
        if not all(proof.get(key) is True for key in
                   ("passed", "recorded_only", "originals_preserved")) or proof.get("case_id") != entry["case_id"]:
            raise ValueError("saved-only identity/acceptance failed")
        entry["saved_diagnostic"] = {"receipt": saved.name, "sha256": sha(saved),
                                     "source": str(source.relative_to(REPO)),
                                     "physical_acceptance_claimed": False}
        print("saved:", suffix, flush=True)
        save(manifest)

    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        attempt = SCRATCH / ("speed-saved-proof-" + suffix + "-v1/v0001/analysis")
        base = [str(PYTHON), str(HERE / "selected_delivery.py"), "--attempt",
                str(attempt), "--case", entry["case_id"]]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
        positive = HERE / ("cpu-selected-delivery-" + suffix + ".log")
        negative = HERE / ("cpu-selected-delivery-negative-" + suffix + ".log")
        codes = []
        for command, log in ((base + ["--allow-diagnostic"], positive), (base, negative)):
            process = subprocess.run(command, cwd=REPO, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(process.stdout.rstrip() + "\n")
            codes.append(process.returncode)
        expected = "synthetic saved source cannot satisfy original delivery"
        if codes[0] != 0 or codes[1] == 0 or expected not in negative.read_text():
            raise ValueError("delivery audit failed: " + suffix)
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "selected_delivery.py", "script_sha256": sha(HERE / "selected_delivery.py"),
            "command": shlex.join(base + ["--allow-diagnostic"]), "test_exit_code": 0,
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": shlex.join(base), "negative_exit_code": codes[1],
            "negative_expected_error": expected, "negative_log": negative.name,
            "negative_log_sha256": sha(negative), "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        print("delivery:", suffix, flush=True)
        save(manifest)


if __name__ == "__main__":
    main()
