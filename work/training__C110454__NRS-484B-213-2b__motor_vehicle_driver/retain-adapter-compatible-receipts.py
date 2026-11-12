"""Retain source-bound compatibility receipts for the 20 corrected candidates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = ROOT / ".runtime-work/c110454-update037-adapter-probe"
PROOFS = HERE / "update037-adapter-proofs"
OUTPUT = HERE / "update037-adapter-retained"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "update037-adapter-probe-manifest.json"
manifest = read(manifest_path)
rows = []
for entry in manifest["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    if suffix.startswith("traversal_"):
        continue
    for candidate in (entry, *entry["candidates"]):
        ident = candidate["id"]
        proof = read(PROOFS / suffix / ident / "proof.json")
        source = RUNS / suffix / ident / "compatibility"
        receipt = read(source / "compatibility.json")
        assert proof["manifest_sha256"] == sha(manifest_path)
        assert proof["construction_sha256"] == candidate["construction_sha256"]
        assert proof["compatibility_log_sha256"] == sha(PROOFS / suffix / ident / "compatibility.log")
        assert receipt["passed"] is True and receipt["case_id"] == entry["case_id"]
        assert receipt["candidate_id"] == ident and receipt["construction_sha256"] == candidate["construction_sha256"]
        assert receipt["negative_removed"] == "statutory_context.json"
        assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
        out = OUTPUT / suffix / ident
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
        rows.append({"case_id": entry["case_id"], "candidate_id": ident,
                     "construction_sha256": candidate["construction_sha256"],
                     "files": files, "diagnostic_only": True})
assert len(rows) == 20
index = {"format": "c110454-adapter-compatible-retention-v1",
         "manifest_sha256": sha(manifest_path), "candidate_count": 20,
         "candidates": rows, "original_native_accepted": False}
target = HERE / "update037-adapter-retained-index.json"
target.write_text(json.dumps(index, indent=2) + "\n")
print(json.dumps({"candidate_count": 20, "index_sha256": sha(target)}))
