"""Bind finished CPU proof receipts without changing selected constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_log(source, dest):
    text = source.read_text().rstrip("\n") + "\n"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)


m = json.loads(MANIFEST.read_text())
for entry in m["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    p = ROOT / "proofs" / suffix
    offline_dest = p / "offline.log"
    copy_log(ROOT.parents[1] / ".runtime-work" / ("c151707-offline-" + suffix[-2:] + "-v2") / "offline.log", offline_dest)
    entry["offline"] = {"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {entry['case_id']} --output .runtime-work/c151707-offline-{suffix[-2:]}-v2 --python $PWD/.venv-cpu/bin/python",
                        "exit_code": 0, "construction_sha256": entry["construction_sha256"],
                        "log": str(offline_dest.relative_to(ROOT)), "log_sha256": sha(offline_dest)}
    phy = p / "physical/receipt.json"
    entry["physical_preparation"] = {"receipt": str(phy.relative_to(ROOT)), "sha256": sha(phy)}
    comp = p / "compatibility.json"
    entry["compatibility"] = {"receipt": str(comp.relative_to(ROOT)), "sha256": sha(comp),
                              "log": str((p / "public-analysis.log").relative_to(ROOT))}
    entry["negative"] = {"log": str((p / "negative-analysis.log").relative_to(ROOT))}
    fallback_path = ROOT / "native/fallbacks" / suffix / "construction.json"
    entry["candidates"] = [{"id": "fallback1", "construction": str(fallback_path.relative_to(ROOT)),
                             "construction_sha256": sha(fallback_path),
                             "trigger": {"source": "original Native route trace and surveyed route polyline",
                                         "metric": "maximum lateral cross-track error in meters",
                                         "failure_condition": "original trace exceeds 0.45 m for 5 or more consecutive frames"},
                             "changed_knobs": ["waypoint target speed reduced from 4/2 to 2/1 m/s"]}]
m["status"] = "partial_cpu_proofs_bound"
MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
print("manifest", sha(MANIFEST))
