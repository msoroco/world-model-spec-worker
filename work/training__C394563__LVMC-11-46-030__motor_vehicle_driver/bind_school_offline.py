"""Bind completed pinned-runtime offline logs to exact draft constructions."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(manifest_name="draft-native-manifest.json", version="v10"):
    path = ROOT / manifest_name
    variant = manifest_name == "draft-variant-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        for candidate in ("primary", "fallback1"):
            target = entry if candidate == "primary" else entry["candidates"][0]
            construction = ROOT / target["construction"]
            if sha(construction) != target["construction_sha256"]:
                raise ValueError("Draft construction changed before offline binding")
            prefix = "c394563-variant-offline" if variant else "c394563-offline"
            source = REPO / ".runtime-work" / f"{prefix}-{suffix}-{candidate}-{version}" / "offline.log"
            log = source.read_text()
            if "Ran 2 tests" not in log or not log.rstrip().endswith("OK"):
                raise ValueError("Pinned offline tests did not pass")
            destination = ROOT / "proofs" / f"{'variant-' if variant else ''}{suffix}-{candidate}-offline.log"
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(log.rstrip() + "\n")
            target["offline"] = {"exit_code": 0,
                "construction_sha256": target["construction_sha256"],
                "command": "runtime.py offline --manifest work/" + ROOT.name +
                    "/" + manifest_name + " --case " + entry["case_id"] +
                    " --candidate " + candidate + " --output .runtime-work/" + prefix + "-" +
                    suffix + "-" + candidate + "-" + version + " --python $PWD/.venv-cpu/bin/python",
                "log": str(destination.relative_to(ROOT)),
                "log_sha256": sha(destination)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"offline_proofs": 2 * len(manifest["cases"]), "manifest_sha256": sha(path)}


if __name__ == "__main__":
    import sys
    print(json.dumps(bind(sys.argv[1] if len(sys.argv) > 1 else "draft-native-manifest.json",
                          sys.argv[2] if len(sys.argv) > 2 else "v10")))
