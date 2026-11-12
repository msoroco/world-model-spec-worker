"""Run pinned offline construction for every absent-reference candidate."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-absent-reference-execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest["cases"]) != 2:
        raise ValueError("Absent-reference pair inventory changed")
    rows = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            folder = HERE / "update024-absent-offline-logs" / suffix
            folder.mkdir(parents=True, exist_ok=True)
            log = folder / (candidate + ".log")
            output = ROOT / ".runtime-work/c110919-update024-absent-offline-matrix" / suffix / candidate
            cmd = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--candidate", candidate, "--output", str(output)]
            run = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log.write_text(run.stdout)
            if run.returncode:
                raise ValueError("Absent-reference offline candidate failed: " + str(log))
            selected = entry if candidate == "primary" else next(x for x in entry["candidates"]
                                                                  if x["id"] == candidate)
            rows.append({"case_id": entry["case_id"], "candidate_id": candidate,
                         "construction_sha256": selected["construction_sha256"],
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log), "exit_code": 0})
            print(json.dumps({"case": suffix, "candidate": candidate, "offline_passed": True}), flush=True)
    summary = {"format": "c110919-absent-reference-offline-matrix-v1",
               "manifest_sha256": sha(MANIFEST), "rows": rows,
               "passed": len(rows), "selected": False}
    path = HERE / "update024-absent-offline-summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"summary_sha256": sha(path), "passed": len(rows)}))


if __name__ == "__main__":
    main()
