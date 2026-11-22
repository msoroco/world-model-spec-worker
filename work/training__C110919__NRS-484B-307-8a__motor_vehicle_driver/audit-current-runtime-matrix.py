"""Independent exact hash and negative-source audit of all 80 CPU chains."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def require(ok, message):
    if not ok:
        raise ValueError(message)

def check(row, entry, candidate, runtime):
    selected = entry if candidate == "primary" else next(
        c for c in entry["candidates"] if c["id"] == candidate)
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    folder = HERE / "current-runtime-selected-proof" / suffix / candidate
    require(row["case_id"] == entry["case_id"] and
            row["candidate_id"] == candidate and
            row["construction_sha256"] == selected["construction_sha256"] and
            row["proof_dir"] == str(folder.relative_to(HERE)) and
            sha(HERE / selected["construction"]) == selected["construction_sha256"],
            "Candidate identity or construction differs")
    compat, saved = folder / "compatibility.json", folder / "saved-processing.json"
    require(sha(compat) == row["compatibility_sha256"] and
            sha(saved) == row["saved_sha256"], "Candidate receipt hash differs")
    c, s = read(compat), read(saved)
    require(c["passed"] is True and c["case_id"] == entry["case_id"] and
            c["candidate_id"] == candidate and
            c["construction_sha256"] == selected["construction_sha256"] and
            c["runtime_manifest_sha256"] == runtime and
            c["log_sha256"] == sha(folder / "analysis.log") and
            c["negative_log_sha256"] == sha(folder / "negative-analysis.log") and
            c["negative_error_contains"] in (folder / "negative-analysis.log").read_text(),
            "Compatibility or negative case-source proof differs")
    require(s["passed"] is True and s["recorded_only"] is True and
            s["originals_preserved"] is True and not s["missing_evidence"] and
            s["case_id"] == entry["case_id"] and s["candidate_id"] == candidate and
            s["native_revision"]["construction_sha256"] == selected["construction_sha256"] and
            s["physical_acceptance_claimed"] is False and
            s["legal_acceptance_claimed"] is False,
            "Recorded-only saved proof differs")
    offline = read(HERE / f"current-runtime-{suffix}-{candidate}-offline.log")
    require(offline["offline_passed"] is True and offline["simulation_started"] is False,
            "Exact offline proof differs")

def main():
    manifest = HERE / "current-runtime-reproof-manifest.json"
    index_path = HERE / "current-runtime-matrix-progress.json"
    m, index = read(manifest), read(index_path)
    runtime = sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json")
    require(m["runtime_manifest_sha256"] == index["runtime_manifest_sha256"] == runtime and
            index["manifest_sha256"] == sha(manifest) and
            index["completed"] == index["required"] == 80 and
            len(m["cases"]) == 20 and len(index["rows"]) == 80,
            "Complete selected current matrix missing")
    expected = [(entry, candidate) for entry in m["cases"]
                for candidate in ("primary", "fallback1", "fallback2", "fallback3")]
    for row, (entry, candidate) in zip(index["rows"], expected):
        check(row, entry, candidate, runtime)
    negatives = {}
    for field in ("case_id", "candidate_id", "compatibility_sha256", "saved_sha256"):
        damaged = copy.deepcopy(index["rows"][0])
        damaged[field] = "wrong"
        try:
            check(damaged, *expected[0], runtime)
        except (ValueError, KeyError) as error:
            negatives[field] = str(error)
        else:
            raise AssertionError("Corrupt matrix row accepted: " + field)
    output = HERE / "current-runtime-matrix-audit.json"
    output.write_text(json.dumps({
        "format": "c110919-current-matrix-audit-v1",
        "manifest_sha256": sha(manifest), "matrix_sha256": sha(index_path),
        "candidate_chains": 80, "negative_rejections": negatives,
        "original_native_accepted": False
    }, indent=2) + "\n")
    print(json.dumps({"candidate_chains": 80, "negative_rejections": 4,
                      "audit_sha256": sha(output)}))

if __name__ == "__main__":
    main()
