"""Offline-check and derive source-bound raw recipes for selected constructions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
RUNTIME = REPO / "runtime.py"
AID = ROOT.name
CASES = ("reference", "contrast", "divided_reference", "divided_opening")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
BASE = REPO / ".runtime-work/update015-c111662-selected/bootstrap"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f"Selected bootstrap failed: {log}: {result.stderr[-1000:]}")
    return result


def build():
    rows = []
    for case in CASES:
        for candidate in CANDIDATES:
            output = BASE / case / candidate
            proof = ROOT / "update015-selected-proof" / case / candidate
            proof.mkdir(parents=True, exist_ok=True)
            if not output.exists():
                command([str(PYTHON), str(RUNTIME), "offline", "--manifest",
                         str(ROOT / "execution-manifest.json"), "--case", AID + "__" + case,
                         "--candidate", candidate, "--output", str(output)],
                        proof / "offline-command.log")
            else:
                # A previous bootstrap can be reused only at the selected
                # construction hash; never silently trust an old materialization.
                manifest = json.loads((ROOT / "execution-manifest.json").read_text())
                entry = next(item for item in manifest["cases"] if item["case_id"] == AID + "__" + case)
                expected = entry["construction_sha256"] if candidate == "primary" else next(
                    item["construction_sha256"] for item in entry["candidates"] if item["id"] == candidate)
                if sha(output / "construction.json") != expected:
                    raise ValueError("Stale selected bootstrap: " + str(output))
            native = output / "work" / AID / "native"
            bundle = native / ("divided-opening" if case.startswith("divided_") else "") / "drafts" / case / candidate
            raw = ROOT / "native/selected-diagnostic" / case / candidate / "raw.json"
            raw.parent.mkdir(parents=True, exist_ok=True)
            code = ("import json,sys; from pathlib import Path; "
                    "sys.path.insert(0,sys.argv[1]); "
                    "from " + ("saved_divided" if case.startswith("divided_") else "saved") +
                    " import make_raw; "
                    "Path(sys.argv[3]).write_text(json.dumps(make_raw(Path(sys.argv[2])),separators=(',',':'))+'\\n')")
            command([str(PYTHON), "-c", code, str(native), str(bundle), str(raw)], proof / "raw-command.log")
            command([str(PYTHON), str(ROOT / "update015-build-current-recipe.py"), case,
                     candidate, "selected"], proof / "recipe-command.log")
            rows.append({"case_id": AID + "__" + case, "candidate_id": candidate,
                         "construction_sha256": sha(output / "construction.json"),
                         "offline_log": str((proof / "offline-command.log").relative_to(ROOT)),
                         "offline_log_sha256": sha(proof / "offline-command.log"),
                         "raw_sha256": sha(raw),
                         "recipe": f"update015-selected-{case if candidate == 'primary' else case+'-'+candidate}-recipe.json"})
            print(json.dumps({"case": case, "candidate": candidate,
                              "offline": True, "recipe": True}), flush=True)
    target = ROOT / "update015-selected-bootstrap-matrix.json"
    target.write_text(json.dumps({"format": "c111662-selected-bootstrap-v1", "rows": rows,
                                  "count": len(rows), "scope": "synthetic CPU only"}, indent=2) + "\n")
    print(json.dumps({"matrix_sha256": sha(target), "count": len(rows)}))


if __name__ == "__main__":
    build()
