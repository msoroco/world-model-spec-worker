"""Retain current package compatibility receipts for the twenty selected primaries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = ROOT / ".runtime-work/c111294-update300-selected-matrix/8e400603c3b5"
SELECTED = HERE / "update300-selected-proofs"
OUT = HERE / "update301-package-compatibility"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
assert len(manifest["cases"]) == 4
for entry in manifest["cases"]:
    suffix = entry["case_id"].removeprefix(HERE.name + "__")
    source = RUNS / suffix / "primary/compatibility"
    receipt = json.loads((source / "compatibility.json").read_text())
    assert receipt["format"] == "worker-package-compatibility"
    assert receipt["passed"] is True and receipt["candidate_id"] == "primary"
    assert receipt["case_id"] == entry["case_id"]
    assert receipt["construction_sha256"] == entry["construction_sha256"]
    assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
    folder = OUT / suffix
    folder.mkdir(parents=True, exist_ok=True)
    copied = {}
    for original, retained in (("compatibility.json", "compatibility.json"),
                               ("compatibility-analysis.log", "analysis.log"),
                               ("negative-analysis.log", "negative.log")):
        destination = folder / retained
        destination.write_bytes((source / original).read_bytes())
        copied[retained] = destination
    assert receipt["log_sha256"] == sha(copied["analysis.log"])
    assert receipt["negative_log_sha256"] == sha(copied["negative.log"])
    rel = lambda path: str(path.relative_to(HERE))
    entry["compatibility"] = {"receipt": rel(copied["compatibility.json"]),
                              "sha256": sha(copied["compatibility.json"]),
                              "log": rel(copied["analysis.log"]),
                              "negative_log": rel(copied["negative.log"])}
    entry["negative"] = {"log": rel(copied["negative.log"]),
                         "log_sha256": sha(copied["negative.log"])}
    offline = SELECTED / suffix / "primary/offline.log"
    assert offline.is_file()
    entry["offline"]["log"] = rel(offline)
    entry["offline"]["log_sha256"] = sha(offline)

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"selected_cases": 4, "manifest_sha256": sha(manifest_path)}))
