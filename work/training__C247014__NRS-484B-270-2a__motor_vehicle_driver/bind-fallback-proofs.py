"""Bind exact fallback offline and public compatibility evidence."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "selected-native-draft-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1":
            raise ValueError("Missing exact fallback")
        version = "-v2" if suffix == "exception_unsafe_available" else ""
        source = REPO / ".runtime-work" / ("c247014-fallback-compat-" + suffix + version)
        receipt = json.loads((source / "compatibility.json").read_text())
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != "fallback1" or
                receipt.get("construction_sha256") != candidate["construction_sha256"] or
                receipt.get("passed") is not True):
            raise ValueError("Fallback compatibility identity differs: " + suffix)
        dest = HERE / "selected-native-draft" / suffix / "fallback1" / "public-proof"
        dest.mkdir(parents=True, exist_ok=True)
        for old, new in (("compatibility.json", "receipt.json"),
                         ("compatibility-analysis.log", "analysis.log"),
                         ("negative-analysis.log", "negative.log")):
            shutil.copyfile(source / old, dest / new)
        candidate["compatibility"] = {
            "receipt": str((dest / "receipt.json").relative_to(HERE)),
            "sha256": sha(dest / "receipt.json"),
            "log": str((dest / "analysis.log").relative_to(HERE)),
            "negative_log": str((dest / "negative.log").relative_to(HERE)),
        }
        log_source = REPO / ".runtime-work" / "c247014-resume-v5" / ("fallback-offline-" + suffix + ".log")
        if not log_source.is_file():
            raise ValueError("Fallback offline log missing: " + suffix)
        dest_log = HERE / "native" / (suffix + "-fallback-offline.log")
        shutil.copyfile(log_source, dest_log)
        candidate["offline"] = {
            "command": ".venv-cpu/bin/python -B runtime.py offline --manifest work/" + HERE.name +
                       "/selected-native-draft-manifest.json --case " + entry["case_id"] +
                       " --candidate fallback1 --output .runtime-work/c247014-fallback-offline-" + suffix +
                       " --python $PWD/.venv-cpu/bin/python",
            "construction_sha256": candidate["construction_sha256"],
            "exit_code": 0,
            "log": str(dest_log.relative_to(HERE)),
            "log_sha256": sha(dest_log),
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"bound": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST)}, sort_keys=True))


if __name__ == "__main__":
    main()
