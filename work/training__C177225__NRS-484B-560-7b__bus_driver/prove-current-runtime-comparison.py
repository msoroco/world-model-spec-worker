"""Reprove all four selected officer-signal saved comparison pairs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        folder = ROOT / ".runtime-work/c177225-current-matrix"
        output = HERE / "current-runtime-comparison" / (candidate + ".json")
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(HERE / "prove_comparison.py"),
                   "--reference", str(folder / "reference" / candidate / "compat"),
                   "--contrast", str(folder / "contrast" / candidate / "compat"),
                   "--output", str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = output.with_suffix(".log")
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError("Comparison failed: " + candidate + " " + result.stderr[-600:])
        proof = json.loads(output.read_text())
        if not (proof["passed"] is True and proof["physical_acceptance_claimed"] is False and
                proof["legal_acceptance_claimed"] is False):
            raise ValueError("Comparison claimed physical or legal acceptance")
        rows.append({"candidate_id": candidate, "receipt": str(output.relative_to(HERE)),
                     "sha256": sha(output), "log": str(log.relative_to(HERE)),
                     "log_sha256": sha(log)})
        print(candidate, "comparison passed", flush=True)
    index = HERE / "current-runtime-comparison-audit.json"
    index.write_text(json.dumps({"format": "c177225-current-comparison-index-v1",
                                 "passed": True, "pairs": rows,
                                 "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"pairs": len(rows), "index_sha256": sha(index)}))


if __name__ == "__main__":
    main()
