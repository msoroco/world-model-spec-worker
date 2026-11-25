"""Select exact production cases only after original sources and CPU receipts exist."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_attempt import verify_review_sources

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(path: str) -> Path:
    target = (HERE / path).resolve()
    if HERE not in target.parents or not target.is_file():
        raise ValueError("Missing assignment source or receipt: " + path)
    return target


def build(assembly_path: Path) -> dict:
    assembly = json.loads(Path(assembly_path).read_text())
    matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    proposals = json.loads((HERE / "proposals/cases.json").read_text())
    expected = set(matrix["accepted_recordings"])
    if assembly.get("assignment_id") != HERE.name or set(assembly.get("cases", {})) != expected:
        raise ValueError("Production assembly must cover every matrix case exactly")
    if ({case["case_id"] for case in plan["cases"]} != expected or
            {case["case_id"] for case in proposals["cases"] if case["target_type"] != "baseline"} != expected or
            proposals.get("sweeps_expanded") is not True):
        raise ValueError("Full statutory case plan and source-grounded sweeps are not expanded")
    entries = []
    for case_id in sorted(expected):
        row = assembly["cases"][case_id]
        site_path = local(row.get("reviewed_site", ""))
        site = json.loads(site_path.read_text())
        if site.get("cell_id") != "C158208" or site.get("review_status") != "reviewed":
            raise ValueError("Original reviewed C158208 site required: " + case_id)
        verify_review_sources(site, site_path, diagnostic_fixture=False)
        construction_path = local(row.get("construction", ""))
        construction = json.loads(construction_path.read_text())
        if (construction.get("case_id") != case_id or
                construction.get("diagnostic_only") is not False or
                construction.get("recording_description") !=
                next(case["recording_description"] for case in proposals["cases"]
                     if case["case_id"] == case_id)):
            raise ValueError("Production construction identity or capture contract differs: " + case_id)
        files = {item["path"]: item["content"] for item in construction["files"]}
        if site_path.name not in files or files[site_path.name] != site_path.read_text():
            raise ValueError("Production bundle omits its reviewed original site: " + case_id)
        for binding in site["source_bindings"].values():
            name = binding["path"]
            if name not in files or files[name] != (site_path.parent / name).read_text():
                raise ValueError("Production bundle omits original survey source: " + name)
        required = ("offline", "physical_preparation", "compatibility", "negative",
                    "measurement_contract", "fixture_recipe", "post_capture",
                    "delivery_acceptance", "native_handoff", "acquisition",
                    "candidate_risk", "candidates", "measurement_procedure")
        if any(key not in row for key in required):
            raise ValueError("Production case lacks exact CPU proof or handoff: " + case_id)
        for field in ("offline", "physical_preparation", "compatibility"):
            receipt = row[field]
            if field == "offline":
                proof = local(receipt["log"])
                if (receipt.get("exit_code") != 0 or
                        receipt.get("construction_sha256") != sha(construction_path) or
                        receipt.get("log_sha256") != sha(proof)):
                    raise ValueError("Exact production offline proof differs: " + case_id)
            else:
                proof = local(receipt["receipt"])
                if receipt.get("sha256") != sha(proof):
                    raise ValueError("Exact production receipt differs: " + case_id)
        entry = {key: value for key, value in row.items() if key != "reviewed_site"}
        entry.update({"case_id": case_id, "kind": "delivery",
                      "construction_sha256": sha(construction_path)})
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    target = HERE / "execution-manifest.json"
    if target.exists():
        raise ValueError("Production selection exists; refuse overwrite")
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"selected_cases": len(entries), "manifest_sha256": sha(target)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assembly", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.assembly), indent=2))
