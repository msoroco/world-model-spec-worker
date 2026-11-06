"""Refresh all exact unselected v1 synthetic package diagnostics."""
from pathlib import Path
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
PROBE = HERE / "probe-package-compatibility.py"


def main():
    env = dict(os.environ)
    env["PATH"] = str(ROOT / ".runtime-work/linux_arm64") + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = str(ROOT / ".runtime-work/geos-wheel/shapely.libs") + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    for suffix in ("controlled_1", "controlled_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            name = "package-compatibility-" + suffix
            if candidate != "primary":
                name += "-" + candidate
            log = HERE / (name + ".log")
            command = [str(PYTHON), str(PROBE), "--suffix", suffix,
                       "--candidate", candidate]
            with log.open("w") as stream:
                result = subprocess.run(command, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=900)
            print(suffix, candidate, "exit", result.returncode, flush=True)
            if result.returncode:
                print(log.read_text()[-2000:], file=sys.stderr)
                raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
