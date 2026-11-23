"""Check current exact delivery and saved-only CPU proof bindings."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
runtime_output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
if not runtime_output.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    if len(manifest["cases"]) != 6:
        raise ValueError("six exact parking cases required")
    for entry in manifest["cases"]:
        validate_case(ROOT, entry, {"full-test"})
        post = entry["post_capture"]
        log = ROOT / post["test_log"]
        if (post.get("recorded_only") is not True or
                post.get("test_exit_code") != 0 or
                hashlib.sha256(log.read_bytes()).hexdigest() !=
                post.get("test_log_sha256")):
            raise ValueError("saved-only CPU binding changed")
        saved = json.loads(log.read_text())
        if (saved.get("passed") is not True or
                saved.get("recorded_only") is not True or
                saved.get("case_id") != entry["case_id"] or
                saved.get("native_revision", {}).get("construction_sha256") !=
                entry["construction_sha256"]):
            raise ValueError("saved-only CPU proof selects another construction")
        print(entry["case_id"], "delivery and saved-only bindings pass")


if __name__ == "__main__":
    main()
