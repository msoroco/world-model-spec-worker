"""Bind current JSON adapter proofs for all eight selected stand candidates."""
import hashlib
import json
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
RUN = ROOT / ".runtime-work/c146314-update804-selected-matrix/34cfd0423100"
PROOFS = HERE / "update804-selected-proofs"
OUT = HERE / "update805-package-compatibility"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(HERE).as_posix()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        for candidate in [entry, *entry["candidates"]]:
            name = candidate.get("id", "primary")
            source = RUN / suffix / name
            proof = PROOFS / suffix / name
            output = OUT / suffix / name
            output.mkdir(parents=True, exist_ok=True)
            receipt = json.loads((source / "compatibility/compatibility.json").read_text())
            if not (receipt["passed"] and receipt["case_id"] == entry["case_id"] and
                    receipt["candidate_id"] == name and
                    receipt["construction_sha256"] == candidate["construction_sha256"] and
                    receipt["negative_removed"] == "native-raw-actors.jsonl"):
                raise ValueError("Source receipt differs: " + suffix + "/" + name)
            for old, new in (("compatibility.json", "compatibility.json"),
                             ("compatibility-analysis.log", "analysis.log"),
                             ("negative-analysis.log", "negative.log")):
                (output / new).write_bytes((source / "compatibility" / old).read_bytes())
            args = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest",
                    str(MANIFEST), "--case", entry["case_id"], "--candidate", name,
                    "--output", str(source / "offline"), "--python", sys.executable]
            candidate["offline"] = {"command": shlex.join(args), "exit_code": 0,
                                    "construction_sha256": candidate["construction_sha256"],
                                    "log": rel(proof / "offline.log"),
                                    "log_sha256": sha(proof / "offline.log")}
            candidate["compatibility"] = {"receipt": rel(output / "compatibility.json"),
                                           "sha256": sha(output / "compatibility.json"),
                                           "log": rel(output / "analysis.log"),
                                           "negative_log": rel(output / "negative.log")}
            if candidate is entry:
                entry["negative"] = {"log": rel(output / "negative.log"),
                                     "log_sha256": sha(output / "negative.log")}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]), "candidates": 8,
                      "manifest_sha256": sha(MANIFEST)}))


if __name__ == "__main__":
    main()
