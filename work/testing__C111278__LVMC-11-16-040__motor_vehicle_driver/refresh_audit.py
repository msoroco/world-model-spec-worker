"""Retain exact-case positive and source-mutation delivery audit proofs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
AUDITOR = ROOT / "delivery_audit.py"
PROBE = ROOT / "audit_probe.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    py = str(REPO / ".venv-cpu/bin/python")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       TMPDIR=str(REPO / ".runtime-work/c111278-owner/tmp"),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c111278-owner/pipeline"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        commands, logs, codes = {}, {}, {}
        for mode in ("positive", "negative"):
            base = REPO / ".runtime-work/c111278-owner"
            version = 0
            while True:
                output = base / f"audit-{suffix}-{mode}-{version}"
                if not output.exists():
                    break
                version += 1
            command = [py, str(PROBE), "--case", entry["case_id"], "--output", str(output)]
            if mode == "negative":
                command.append("--negative")
            run = subprocess.run(command, cwd=REPO, env=environment, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = ROOT / f"audit-{suffix}-{mode}.log"
            log.write_text("\n".join(line.rstrip() for line in run.stdout.splitlines()).rstrip() + "\n")
            commands[mode], logs[mode], codes[mode] = " ".join(command), log, run.returncode
        expected = "overview bytes missing or changed"
        if (codes["positive"] != 0 or codes["negative"] == 0 or
                expected not in logs["negative"].read_text()):
            raise RuntimeError(f"{suffix}: positive/negative audit failed")
        positive = json.loads(logs["positive"].read_text())
        decoded = positive["result"]["full_video_decode"]
        if (positive["scope"] != "synthetic_cpu_audit_probe" or
                set(decoded) != {"overview", "approach", "reference_corner", "driver_reference"} or
                any(item["decoded_frames"] != 900 for item in decoded.values())):
            raise ValueError("four 900-frame videos were not fully decoded")
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": AUDITOR.name, "script_sha256": sha(AUDITOR),
            "command": commands["positive"], "test_exit_code": 0,
            "test_log": logs["positive"].name, "test_log_sha256": sha(logs["positive"]),
            "negative_command": commands["negative"],
            "negative_exit_code": codes["negative"],
            "negative_expected_error": expected,
            "negative_log": logs["negative"].name,
            "negative_log_sha256": sha(logs["negative"])}
        print(suffix, "delivery audit passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
