"""Seal selected source-gated candidate CPU compatibility without physical claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c158208-owner-nov26b/deferred-compat-v3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal() -> dict:
    manifest = json.loads((HERE / "execution-manifest.source-gated-draft.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        kind = entry["case_id"].split("__")[-1]
        candidates = []
        for candidate in ("primary", "fallback1"):
            source = SCRATCH / kind / candidate
            proof = json.loads((source / "compatibility.json").read_text())
            target = HERE / "cases" / kind / ("fallback1" if candidate == "fallback1" else "primary")
            target.mkdir(parents=True, exist_ok=True)
            for source_name, target_name in (("compatibility.json", "compatibility.json"),
                                             ("compatibility-analysis.log", "cpu-analysis.log"),
                                             ("negative-analysis.log", "negative-analysis.log")):
                (target / target_name).write_bytes((source / source_name).read_bytes())
            if (proof["case_id"] != entry["case_id"] or proof["candidate_id"] != candidate or
                    proof["construction_sha256"] != (entry["construction_sha256"] if candidate == "primary" else entry["candidates"][0]["construction_sha256"]) or
                    proof["passed"] is not True or
                    proof["log_sha256"] != sha(target / "cpu-analysis.log") or
                    proof["negative_log_sha256"] != sha(target / "negative-analysis.log")):
                raise ValueError("stale exact compatibility: " + kind + " " + candidate)
            spec = {"receipt": str((target / "compatibility.json").relative_to(HERE)),
                    "sha256": sha(target / "compatibility.json"),
                    "log": str((target / "cpu-analysis.log").relative_to(HERE)),
                    "negative_log": str((target / "negative-analysis.log").relative_to(HERE))}
            if candidate == "primary":
                entry["compatibility"] = spec
                entry["negative"] = {"log": spec["negative_log"]}
            else:
                entry["candidates"][0]["compatibility"] = spec
            candidates.append({"id": candidate, "construction_sha256": proof["construction_sha256"],
                               "receipt": spec["receipt"], "receipt_sha256": spec["sha256"],
                               "log_sha256": proof["log_sha256"],
                               "negative_log_sha256": proof["negative_log_sha256"]})
        rows.append({"case_id": entry["case_id"], "candidates": candidates})
    (HERE / "execution-manifest.source-gated-draft.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    index = {"format": "c158208-source-gated-compatibility-index-v1",
             "assignment_id": HERE.name, "scope": "synthetic_fixture_cpu_only",
             "selected_manifest_status": "draft_not_delivery_ready", "cases": rows,
             "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    output = HERE / "deferred-source-compatibility-index.json"
    output.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    return {"candidate_receipts": sum(len(row["candidates"]) for row in rows),
            "index_sha256": sha(output), "draft_manifest_sha256": sha(HERE / "execution-manifest.source-gated-draft.json")}


if __name__ == "__main__":
    print(json.dumps(seal(), indent=2))
