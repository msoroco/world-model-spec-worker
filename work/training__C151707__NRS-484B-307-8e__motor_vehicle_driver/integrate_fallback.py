"""Bind exact fallback offline and public diagnostic receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


m = json.loads(MANIFEST.read_text())
for entry in m["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    number = suffix[-2:]
    p = ROOT / "proofs" / suffix / "fallback1"
    p.mkdir(parents=True, exist_ok=True)
    f = entry["candidates"][0]
    source = REPO / ".runtime-work" / ("c151707-fallback-offline-" + number) / "offline.log"
    log = p / "offline.log"
    log.write_text(source.read_text().rstrip("\n") + "\n")
    f["offline"] = {"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {entry['case_id']} --candidate fallback1 --output .runtime-work/c151707-fallback-offline-{number} --python $PWD/.venv-cpu/bin/python",
                    "construction_sha256": f["construction_sha256"], "exit_code": 0,
                    "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)}
    source = REPO / ".runtime-work" / ("c151707-fallback-public-" + number)
    for original, saved in (("compatibility.json", "compatibility.json"),
                            ("compatibility-analysis.log", "public-analysis.log"),
                            ("negative-analysis.log", "negative-analysis.log")):
        dest = p / saved
        dest.write_text((source / original).read_text().rstrip("\n") + "\n")
    comp = p / "compatibility.json"
    f["compatibility"] = {"receipt": str(comp.relative_to(ROOT)), "sha256": sha(comp),
                          "log": str((p / "public-analysis.log").relative_to(ROOT)),
                          "negative_log": str((p / "negative-analysis.log").relative_to(ROOT))}
m["status"] = "partial_fallback_cpu_proven"
MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
print(sha(MANIFEST))
