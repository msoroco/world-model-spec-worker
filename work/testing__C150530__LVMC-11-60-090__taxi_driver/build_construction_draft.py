"""Build exact-case CPU bundle drafts for pinned offline materialization.

The draft manifest deliberately omits readiness receipts and cannot satisfy
the strict delivery gate. It allows the pinned offline command to exercise the
real source inventory before semantic and documentary review is complete.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from recording_description import build as recording_description

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"
CASES = ("near_stand", "far_stand", "near_stand_straight")
CODE = ("stand_route.py", "candidate_opendrive.py", "reviewed_context.py",
        "native_trace_capture.py", "turn_trace_finalizer.py", "taxi_native_motion.py",
        "taxi_cameras.py", "taxi_capture_ticks.py", "saved_turn_check.py",
        "delivery_audit.py", "four_view_composition.py", "turn_pair_audit.py",
        "saved_case_analysis.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(case: str) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact case")
    case_id = ASSIGNMENT + "__" + case
    layout = ROOT / "candidates" / (case + ".json")
    map_path = ROOT / "candidates" / (case + ".xodr")
    config = {
        "law_id": "LVMC-11-60-090", "cell_id": "C150530", "actor": "taxi_driver",
        "selected_case_id": case_id, "case": {"case_id": case_id},
        "rate_hz": 20, "duration_s": 35,
        "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
        "context_packet": "reviewed-context.json",
        "candidate_map": "candidates/" + case + ".xodr",
        "candidate_map_sha256": sha(map_path),
        "candidate_layout": "candidates/" + case + ".json",
        "source_packets": [], "required_atoms": [],
        "documentary_status": "original designated-stand and notice sources unbound",
    }
    files = []
    for bundled, source in (("runner.py", ROOT / "taxi_runner.py"),
                            ("config.json", None),
                            ("candidates/" + case + ".json", layout),
                            ("candidates/" + case + ".xodr", map_path),
                            ("tests/test_bundle.py", ROOT / "offline_bundle_test.py"),
                            *((name, ROOT / name) for name in CODE)):
        content = json.dumps(config, indent=2) + "\n" if source is None else source.read_text()
        entry = {"path": bundled, "content": content}
        if source is not None:
            entry["source"] = source.relative_to(REPO).as_posix()
        files.append(entry)
    return {
        "law_id": "LVMC-11-60-090", "cell_id": "C150530", "actor": "taxi_driver",
        "case_id": case_id, "entrypoint": "runner.py", "files": files,
        "recording_description": recording_description(),
        "status": "draft_offline_bundle; not delivery-ready",
    }


def main() -> None:
    entries = []
    for case in CASES:
        path = ROOT / "cases" / case / "construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(build(case), indent=2) + "\n")
        entries.append({"case_id": ASSIGNMENT + "__" + case, "kind": "delivery",
                        "construction": path.relative_to(ROOT).as_posix(),
                        "construction_sha256": sha(path),
                        "measurement_contract": (Path("cases") / case /
                                                 "selected-measurement-contract.json").as_posix(),
                        "measurement_procedure": {"entrypoint": "saved_case_analysis.py"},
                        "proof_status": "draft_offline_only"})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
                "cases": entries, "status": "draft; not strict delivery-ready"}
    (ROOT / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
