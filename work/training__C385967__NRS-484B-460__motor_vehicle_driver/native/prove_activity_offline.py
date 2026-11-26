"""Run pinned offline construction checks for every statutory activity candidate."""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name


def main():
    manifest = HERE / "selected-draft-manifest.json"
    for action in ("stop", "stand"):
        for letter in "ab":
            case = ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}"
            for candidate in ("primary", "fallback1"):
                prefix = f"selected-{action}-{letter}-{candidate}"
                output = ROOT / ".runtime-work" / f"c385967-{action}-{letter}-{candidate}-offline2"
                command = [sys.executable, "-B", str(ROOT / "runtime.py"), "offline",
                    "--manifest", str(manifest), "--case", case,
                    "--candidate", candidate, "--output", str(output)]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
                log = HERE / f"{prefix}-offline.log"
                log.write_text((result.stdout + result.stderr).rstrip() + "\n")
                if result.returncode:
                    raise ValueError(f"{prefix} offline failed: " + log.read_text()[-2000:])
                receipt = json.loads(result.stdout)
                if receipt.get("offline_passed") is not True:
                    raise ValueError(f"{prefix} did not pass")
                print(json.dumps({"case_id": case, "candidate": candidate,
                    "offline_passed": True}), flush=True)


if __name__ == "__main__":
    main()
