"""Run revision-selected saved-only processing on exact diagnostic sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c202480-owner/saved"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(command: list[str], env: dict, log: Path, timeout: int = 600,
         expected_error: str | None = None) -> int:
    done = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                          text=True, timeout=timeout)
    log.write_text((done.stdout + done.stderr).rstrip("\n") + "\n")
    if expected_error is not None:
        if done.returncode == 0 or expected_error not in log.read_text():
            raise ValueError("saved negative did not reject original source")
    elif done.returncode:
        raise ValueError("saved command failed: " + done.stderr[-1000:])
    return done.returncode


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT),
               TMPDIR=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        compatible = REPO / ".runtime-work/c202480-owner" / (
            "compat-inside-15-v5" if suffix == "inside_15" else "compat-" + suffix + "-positive")
        proof = json.loads((compatible / "compatibility.json").read_text())
        base = ROOT / suffix
        if base.exists():
            shutil.rmtree(base)
        base.mkdir()
        summaries = []
        for negative in (False, True):
            label = "negative" if negative else "positive"
            attempt = base / (label + "-attempt")
            versions = base / (label + "-versions")
            runtime = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py")]
            call(runtime + ["materialize", "--manifest", str(manifest_path),
                            "--case", entry["case_id"], "--output", str(attempt)],
                 env, base / (label + "-materialize.log"))
            for name in proof["fixture_manifest"]:
                p = compatible / name
                target = attempt / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
            if negative:
                damaged = attempt / "native-stop-device.json"
                damaged.write_text(damaged.read_text().rstrip("\n") + " \n")
            command = runtime + ["process-saved", "--manifest", str(manifest_path),
                                 "--case", entry["case_id"], "--attempt", str(attempt),
                                 "--output", str(versions), "--library",
                                 str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
            log = HERE / ("saved-" + suffix + "-" + label + ".log")
            exit_code = call(command, env, log,
                             expected_error="source hash differs: native_stop_device"
                             if negative else None)
            if negative:
                summaries.append({"kind": label,
                                  "expected_error": "source hash differs: native_stop_device",
                                  "command": " ".join(command).replace(str(REPO) + "/", ""),
                                  "exit_code": exit_code,
                                  "log": log.name, "log_sha256": sha(log)})
                continue
            record = json.loads((versions / "v0001/processing.json").read_text())
            if record.get("recorded_only") is not True or record.get("originals_preserved") is not True:
                raise ValueError("saved-only source preservation missing")
            if record.get("missing_evidence") is not False:
                raise ValueError("positive saved analysis has missing evidence")
            receipt = HERE / ("saved-" + suffix + "-" + label + ".json")
            receipt.write_text(json.dumps(record, separators=(",", ":")) + "\n")
            summaries.append({"kind": label, "receipt": receipt.name,
                              "receipt_sha256": sha(receipt),
                              "command": " ".join(command).replace(str(REPO) + "/", ""),
                              "exit_code": exit_code, "log": log.name,
                              "log_sha256": sha(log)})
        entry["saved_processing"] = {"positive": summaries[0], "negative": summaries[1]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "saved-only positive and source rejection passed", flush=True)


if __name__ == "__main__":
    main()
