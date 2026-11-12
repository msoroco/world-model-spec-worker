"""Run the existing 40-bundle proof against the revised exact descriptions."""
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update058-selected-ordinary-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("ordinary_matrix", HERE / "run-ten-case-probe.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.MANIFEST = MANIFEST
    runner.RUN_ROOT = ROOT / ".runtime-work/c110919-update058-selected-ordinary-matrix"
    runner.PROOFS = HERE / "selected_ordinary_cases/receipts"
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    if len(entries) != 10 or manifest["stage_sha256"] != sha(HERE / "proposals/cases.json"):
        raise ValueError("Selected ordinary manifest or stage changed")
    jobs = [(entry, "primary", entry) for entry in entries]
    jobs += [(entry, candidate["id"], candidate) for entry in entries
             for candidate in entry["candidates"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: runner.task(*job), jobs))
    index = {"format": "c110919-selected-ordinary-pinned-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "stage_sha256": manifest["stage_sha256"],
             "cases": len(entries), "candidates": len(results), "results": results,
             "original_native_accepted": False}
    path = HERE / "update058-selected-ordinary-matrix-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": len(entries), "candidates": len(results),
                      "index_sha256": sha(path)}))


if __name__ == "__main__":
    main()
