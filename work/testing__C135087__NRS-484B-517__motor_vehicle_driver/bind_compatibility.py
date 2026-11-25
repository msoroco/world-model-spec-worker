"""Bind exact synthetic compatibility receipts to the selected case manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SCRATCH = REPO / ".runtime-work" / "c135087-compat-v11"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        for candidate in ("primary", "fallback1"):
            source = SCRATCH / (suffix + "-" + candidate)
            receipt = json.loads((source / "compatibility.json").read_text())
            assert receipt["passed"] is True and receipt["case_id"] == entry["case_id"]
            assert receipt["candidate_id"] == candidate
            target = HERE / "proofs" / ("selected-" + suffix + "-" + candidate)
            target.mkdir(parents=True, exist_ok=True)
            names = {"compatibility.json": "receipt.json",
                     "compatibility-analysis.log": "analysis.log",
                     "negative-analysis.log": "negative.log"}
            for original, renamed in names.items():
                shutil.copyfile(source / original, target / renamed)
            assert receipt["log_sha256"] == sha(target / "analysis.log")
            assert receipt["negative_log_sha256"] == sha(target / "negative.log")
            relative = target.relative_to(HERE)
            spec = {"receipt": str(relative / "receipt.json"),
                    "sha256": sha(target / "receipt.json"),
                    "log": str(relative / "analysis.log"),
                    "negative_log": str(relative / "negative.log")}
            if candidate == "primary":
                entry["compatibility"] = {key: spec[key] for key in ("receipt", "sha256", "log")}
                entry["negative"] = {"log": spec["negative_log"]}
            else:
                fallback = next(item for item in entry["candidates"] if item["id"] == candidate)
                fallback["compatibility"] = spec
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print("bound", len(manifest["cases"]), "primary and fallback compatibility pairs")


if __name__ == "__main__":
    bind()
