"""Retain the four rail-at compatibility receipts and negatives under work/."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = ROOT / ".runtime-work/c110454-update035-seven-probe/rail_at"
PROOFS = HERE / "update035-probe-proofs/rail_at"
OUTPUT = HERE / "update035-rail-at-retained"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "update035-seven-case-probe-manifest.json"
manifest = read(manifest_path)
entry = next(x for x in manifest["cases"] if x["case_id"].endswith("__rail_at"))
rows = []
for candidate in (entry, *entry["candidates"]):
    ident = candidate["id"]
    proof = read(PROOFS / ident / "proof.json")
    source = RUNS / ident / "compatibility"
    receipt = read(source / "compatibility.json")
    assert proof["manifest_sha256"] == sha(manifest_path)
    assert proof["construction_sha256"] == candidate["construction_sha256"]
    assert proof["compatibility_log_sha256"] == sha(PROOFS / ident / "compatibility.log")
    assert receipt["passed"] is True and receipt["case_id"] == entry["case_id"]
    assert receipt["candidate_id"] == ident and receipt["construction_sha256"] == candidate["construction_sha256"]
    assert receipt["negative_removed"] == "statutory_context.json"
    assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
    out = OUTPUT / ident
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for source_name, target_name in (("compatibility.json", "compatibility.json"),
                                     ("compatibility-analysis.log", "analysis.log"),
                                     ("negative-analysis.log", "negative.log")):
        target = out / target_name
        content = (source / source_name).read_bytes()
        if target.exists():
            assert target.read_bytes() == content
        else:
            target.write_bytes(content)
        files[source_name] = {"path": str(target.relative_to(HERE)), "sha256": sha(target)}
    assert receipt["log_sha256"] == files["compatibility-analysis.log"]["sha256"]
    assert receipt["negative_log_sha256"] == files["negative-analysis.log"]["sha256"]
    rows.append({"candidate_id": ident, "construction_sha256": candidate["construction_sha256"],
                 "files": files, "diagnostic_only": True})
index = {"format": "c110454-rail-at-retained-compatibility-v1",
         "manifest_sha256": sha(manifest_path), "case_id": entry["case_id"],
         "candidate_count": 4, "candidates": rows, "original_native_accepted": False}
target = HERE / "update035-rail-at-retained-index.json"
target.write_text(json.dumps(index, indent=2) + "\n")
print(json.dumps({"candidate_count": 4, "index_sha256": sha(target)}))
