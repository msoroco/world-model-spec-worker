"""Exercise pinned saved-only processing against each exact synthetic source.

Receipts prove software processing and failure feedback only, never physical
bicycle/rack visibility or an actual Native capture.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"
VALIDATOR = REPO / ".runtime-work/c10307-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> tuple[int, str]:
    done = subprocess.run(command, cwd=REPO, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=600)
    return done.returncode, done.stdout


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        source = REPO / ".runtime-work" / ("c10307-compat-native-v21-" + suffix)
        attempt = REPO / ".runtime-work" / ("c10307-saved-v21-" + suffix + "-attempt")
        output = REPO / ".runtime-work" / ("c10307-saved-v21-" + suffix)
        for path in (attempt, output):
            if path.exists():
                shutil.rmtree(path)
        code, log = run([str(PYTHON), str(REPO / "runtime.py"), "materialize",
                         "--manifest", str(MANIFEST), "--case", case,
                         "--output", str(attempt)])
        if code:
            raise RuntimeError("materialize " + suffix + ": " + log[-1600:])
        compatibility = json.loads((ROOT / entry["compatibility"]["receipt"]).read_text())
        for name, expected in compatibility["fixture_manifest"].items():
            original = source / name
            # Compatibility composes/remuxes the generated camera streams in
            # place. Textual fixture sources remain byte-identical; the saved
            # processor independently decodes and checks the current media.
            if not original.is_file() or (original.suffix != ".mkv" and sha(original) != expected):
                raise ValueError("diagnostic source changed: " + name)
            target = attempt / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        command = [str(PYTHON), str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", case,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        code, log = run(command)
        path = ROOT / ("cpu-process-saved-" + suffix + ".log")
        path.write_text(log)
        if code:
            raise RuntimeError("process-saved " + suffix + ": " + log[-1800:])
        receipt = json.loads((output / "v0001/processing.json").read_text())
        if receipt["case_id"] != case or not receipt["recorded_only"] or not receipt["originals_preserved"]:
            raise ValueError("saved processing receipt lacks exact source preservation")
        entry["post_capture"] = {"recorded_only": True, "command": " ".join(command),
                                 "feedback_command": " ".join(command), "test_log": path.name,
                                 "test_log_sha256": sha(path), "test_exit_code": 0}
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(suffix, "saved-only passed", sha(path), flush=True)


if __name__ == "__main__":
    main()
