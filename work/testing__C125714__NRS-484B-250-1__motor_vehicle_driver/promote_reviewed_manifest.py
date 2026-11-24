"""Promote seven reviewed delivery candidates only after CPU proof binding.

This assembles a canonical manifest from operator-supplied reviewed candidates
and stage receipts. It does not infer source authority or physical acceptance.
The pinned worker gate remains the independent acceptance check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reviewed_delivery_author import SUFFIXES

ROOT = Path(__file__).resolve().parent
REQUIRED = ("offline", "physical_preparation", "compatibility", "negative",
            "saved_processing", "delivery_acceptance")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("receipt path must be candidate-relative")
    raw = root / relative
    path = raw.resolve()
    if raw.is_symlink() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("receipt source missing or escaping candidate root")
    return path


def assemble(candidate_root: Path, receipt_index: Path, *, allow_scratch: bool = False) -> dict:
    candidate_root = candidate_root.resolve()
    receipt_index = receipt_index.resolve(strict=True)
    if not allow_scratch and not candidate_root.is_relative_to(ROOT):
        raise ValueError("reviewed candidates must be returned in own assignment")
    index = json.loads((candidate_root / "candidate-index.json").read_text())
    if index.get("format") != "worker-reviewed-delivery-candidates" or index.get("assignment_id") != ROOT.name:
        raise ValueError("reviewed candidate index identity mismatch")
    cases = index.get("cases", [])
    exact = {ROOT.name + "__" + suffix for suffix in SUFFIXES}
    if len(cases) != len(exact) or {row.get("case_id") for row in cases} != exact:
        raise ValueError("reviewed candidate index lacks seven exact cases")
    proof = json.loads(receipt_index.read_text())
    if proof.get("assignment_id") != ROOT.name or set(proof.get("cases", {})) != exact:
        raise ValueError("receipt index lacks seven exact cases")
    result = {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
              "runtime_manifest_sha256": index.get("runtime_manifest_sha256"),
              "cases": []}
    returned_root = candidate_root if allow_scratch else ROOT
    for entry in cases:
        case_id = entry["case_id"]
        if entry.get("kind") != "delivery":
            raise ValueError("reviewed case must be delivery")
        construction = bound(candidate_root, entry.get("construction"))
        if sha(construction) != entry.get("construction_sha256"):
            raise ValueError("reviewed construction hash changed: " + case_id)
        document = json.loads(construction.read_text())
        if document.get("diagnostic_only") is not False or document.get("case_id") != case_id:
            raise ValueError("diagnostic or wrong reviewed construction: " + case_id)
        preflight = bound(candidate_root if allow_scratch else ROOT.parents[1], entry.get("source_preflight"))
        source_check = json.loads(preflight.read_text())
        if source_check.get("passed") is not True or source_check.get("case_id") != case_id or source_check.get("native_started") is not False:
            raise ValueError("reviewed source preflight is incomplete: " + case_id)
        stage = proof["cases"][case_id]
        for name in REQUIRED:
            item = stage.get(name)
            if not isinstance(item, dict) or not item.get("receipt") or not item.get("sha256"):
                raise ValueError("missing " + name + " receipt: " + case_id)
            path = bound(returned_root, item["receipt"])
            if sha(path) != item["sha256"]:
                raise ValueError("changed " + name + " receipt: " + case_id)
            detail = json.loads(path.read_text())
            if detail.get("case_id") != case_id or detail.get("construction_sha256") != entry["construction_sha256"]:
                raise ValueError("stale " + name + " case or construction binding: " + case_id)
        promoted = dict(entry)
        promoted.update(stage)
        promoted["construction"] = str(construction.relative_to(returned_root))
        promoted["measurement_contract"] = str(bound(candidate_root, entry.get("measurement_contract")).relative_to(returned_root))
        for alternate in promoted.get("candidates", []):
            alternate["construction"] = str(bound(candidate_root, alternate.get("construction")).relative_to(returned_root))
        result["cases"].append(promoted)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().parent != ROOT or args.output.name != "execution-manifest.json" or args.output.exists():
        parser.error("canonical manifest must be a fresh file in this assignment")
    result = assemble(args.candidates, args.receipts)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
