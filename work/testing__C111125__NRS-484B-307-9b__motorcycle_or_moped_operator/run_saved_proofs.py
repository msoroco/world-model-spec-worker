"""Exercise saved-only processing for each source-hashed diagnostic case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / ".runtime-work" / "c111125_9b_owner_nov24d"
MANIFEST = FOLDER / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu" / "bin" / "python"
RUNTIME = REPO / "runtime.py"
VALIDATOR = REPO / ".runtime-work" / "c110969-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def run(command: list[str], log: Path, env: dict[str, str]) -> None:
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"Exit {result.returncode}: {command}; {log.read_text()[-1500:]}")


def main(suffixes: list[str]) -> None:
    env = dict(os.environ, TMPDIR=str(SCRATCH.resolve()),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str((SCRATCH / "output").resolve()),
               PYTHONDONTWRITEBYTECODE="1")
    for suffix in suffixes:
        fixture = SCRATCH / f"saved-fixture-{suffix}"
        attempt = SCRATCH / f"saved-attempt-post-{suffix}"
        output = SCRATCH / f"saved-post-{suffix}"
        case = FOLDER.name + "__" + suffix
        if not fixture.exists():
            run([str(PYTHON), str(RUNTIME), "fixture", "--recipe",
                 str(FOLDER / "diagnostics" / f"{suffix}-recipe.json"), "--output",
                 str(fixture)], SCRATCH / f"saved-fixture-{suffix}.raw", env)
        if not attempt.exists():
            run([str(PYTHON), str(RUNTIME), "materialize", "--manifest",
                 str(MANIFEST), "--case", case, "--output", str(attempt)],
                SCRATCH / f"saved-materialize-{suffix}.raw", env)
            for source in fixture.iterdir():
                target = attempt / source.name
                if target.exists():
                    raise RuntimeError("Fixture shadows materialized source: " + source.name)
                if source.is_dir():
                    import shutil
                    shutil.copytree(source, target)
                else:
                    import shutil
                    shutil.copy2(source, target)
        command = [str(PYTHON), str(RUNTIME), "process-saved", "--manifest",
                   str(MANIFEST), "--case", case, "--attempt", str(attempt),
                   "--output", str(output), "--library", str(REPO / "runtime" / "library"),
                   "--validator", str(VALIDATOR)]
        raw_log = SCRATCH / f"saved-{suffix}.raw"
        run(command, raw_log, env)
        clean = "\n".join(line.rstrip() for line in raw_log.read_text().rstrip().splitlines()) + "\n"
        log = FOLDER / f"saved-{suffix}.log"
        log.write_text(clean)
        data = json.loads(MANIFEST.read_text())
        entry = next(item for item in data["cases"] if item["case_id"] == case)
        entry["post_capture"] = {
            "command": " ".join(command), "feedback_command": " ".join(command),
            "recorded_only": True, "test_exit_code": 0, "test_log": log.name,
            "test_log_sha256": hashlib.sha256(clean.encode()).hexdigest(),
        }
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
        receipt = json.loads((output / "v0001" / "processing.json").read_text())
        print(suffix, "saved-only", receipt["originals_preserved"],
              "frames", receipt["timestamp_joins"]["frames"], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
