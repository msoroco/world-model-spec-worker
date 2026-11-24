"""Bind completed exact diagnostic receipts to the selected draft manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(path.read_text())
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            tag = "" if candidate == "primary" else "fallback1-"
            scratch_tag = suffix if candidate == "primary" else "fallback1-" + suffix
            source = SCRATCH / ("c129731-compat-" + scratch_tag + "-v12")
            receipt = json.loads((source / "compatibility.json").read_text())
            construction = (entry if candidate == "primary" else entry["candidates"][0])
            if (receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"]
                    or receipt.get("candidate_id") != candidate
                    or receipt.get("construction_sha256") != construction["construction_sha256"]):
                raise ValueError("Stale compatibility receipt: " + scratch_tag)
            receipt_name = "cpu-compatibility-" + tag + suffix + ".json"
            log_name = "cpu-compat-analysis-" + tag + suffix + ".log"
            negative_name = "negative-compat-" + tag + suffix + ".log"
            for original, target in (("compatibility.json", receipt_name),
                                     ("compatibility-analysis.log", log_name),
                                     ("negative-analysis.log", negative_name)):
                (HERE / target).write_bytes((source / original).read_bytes())
            if (sha(HERE / log_name) != receipt["log_sha256"] or
                    sha(HERE / negative_name) != receipt["negative_log_sha256"]):
                raise ValueError("Compatibility logs differ: " + scratch_tag)
            spec = {"receipt": receipt_name, "sha256": sha(HERE / receipt_name),
                    "log": log_name, "negative_log": negative_name}
            construction["compatibility"] = spec
            command = (".venv-cpu/bin/python runtime.py compatibility --manifest "
                       + str(HERE.relative_to(REPO) / path.name) + " --case " + entry["case_id"]
                       + ("" if candidate == "primary" else " --candidate fallback1")
                       + " --output " + str(source.relative_to(REPO))
                       + " --library runtime/library --validator "
                       + ".runtime-work/c129731-decoder-v1/.lake/build/bin/adapterCheck")
            row = {"command": command, "exit_code": 0, "log": receipt_name,
                   "sha256": spec["sha256"]}
            result["tests"] = [item for item in result["tests"]
                               if item["log"] != receipt_name] + [row]
            print(scratch_tag, spec["sha256"])
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    build()
