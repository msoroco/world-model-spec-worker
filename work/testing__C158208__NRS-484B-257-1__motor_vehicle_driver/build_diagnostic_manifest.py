"""Bind generated fixtures to the exact C158208 diagnostic software path.

This manifest is deliberately not the source-gated delivery manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from build_semantic_proposals import recording_description

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("nearest_view_response", "nearest_view_uninterrupted")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    cases = []
    for kind in KINDS:
        original = json.loads((HERE / f"construction-{kind}.json").read_text())
        if original.get("diagnostic_only") is not True:
            raise ValueError("diagnostic source construction changed")
        files = {item["path"]: item["content"] for item in original["files"]}
        for name in ("analysis.py", "prepare_derived_media.py"):
            files[name] = (HERE / name).read_text(encoding="utf-8")
        original["recording_description"] = recording_description()
        original["files"] = [{"path": name, "content": code}
                             for name, code in files.items()]
        target = HERE / f"construction-compatibility-{kind}.json"
        target.write_text(json.dumps(original, indent=2, ensure_ascii=False) + "\n")
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("returned diagnostic construction too large")
        cases.append({
            "case_id": HERE.name + "__" + kind,
            "kind": "capability_research",
            "construction": target.name,
            "construction_sha256": sha(target),
            "fixture_recipe": f"work/{HERE.name}/fixture-recipe-{kind}.json",
            "measurement_contract": f"measurement-contract-{kind}.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
        })
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": HERE.name,
        "status": "diagnostic_compatibility_only_original_source_pending",
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "cases": cases,
    }
    target = HERE / "execution-manifest.diagnostic.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"manifest": target.name, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
