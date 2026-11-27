"""Materialize a source-gated police-direction comparison draft."""
import hashlib
import json
from pathlib import Path

from build_package import recording_description

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native"
AID = ROOT.name
PREFIX = AID + "__selected_police_source__"
SUFFIXES = ("police_absent", "police_present")
CASE_IDS = [PREFIX + name for name in SUFFIXES]
CODE = {"runner.py": "branch_runner.py", "branch_context.py": "branch_context.py",
        "geometry.py": "geometry.py", "measure_obstruction.py": "measure_obstruction.py",
        "source_join.py": "source_join.py", "finalize.py": "finalize.py"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads((NATIVE / "config-condition_a.json").read_text())
    description = recording_description()
    entries = [{"path": target, "content": (NATIVE / origin).read_text()}
               for target, origin in CODE.items()]
    entries.append({"path": "tests/test_bundle.py",
                    "content": (ROOT / "tests/test_bundle.py").read_text()})
    cases = []
    for suffix in SUFFIXES:
        case_id = PREFIX + suffix
        cfg = dict(source, case_id=case_id, selected_case_id=case_id,
                   supported_case_ids=CASE_IDS, required_atoms=[], source_packets=[],
                   recording_description=description, park_y_m=-1.1,
                   activity_request="park",
                   exception_request="police_direction" if suffix == "police_present" else None)
        construction = {"case_id": case_id, "law_id": "NRS-484B-450-1k",
                        "cell_id": "C135702", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py",
                        "files": entries + [{"path": "config.json", "content": json.dumps(cfg, indent=2) + "\n"}],
                        "measurement_plan": {"entrypoint": "finalize.py",
                                             "required_sources": ["native_samples.jsonl", "camera-frames.jsonl",
                                                                  "exception-context.json", "obstruction-inventory.json",
                                                                  "road.xodr", "video_frames.jsonl"],
                                             "source_review_required": True},
                        "recording_description": description,
                        "static_checks": ["Exact NRS 484B.450(1)(k) and C135702 identity",
                                          "fixed parked geometry and one police-source comparison axis",
                                          "600 original frames at 20 Hz with four synchronized cameras"],
                        "termination_rules": ["600 original frames", "restore Native world and owned actors"],
                        "mechanisms": ["source-gated operator activity and separately hashed four exception records",
                                       "physical barrier and parked/passing vehicle source readback"],
                        "status": "branch_draft_original_capture_pending"}
        path = ROOT / "cases" / suffix / "construction.json"
        digest = write(path, construction)
        cases.append({"case_id": case_id, "kind": "delivery",
                      "construction": str(path.relative_to(ROOT)),
                      "construction_sha256": digest})
    write(ROOT / "police-pair-draft-manifest.json",
          {"format": "worker-execution-manifest", "assignment_id": AID,
           "runtime_manifest_sha256": json.loads((ROOT / "execution-manifest.json").read_text())["runtime_manifest_sha256"],
           "status": "offline_branch_draft", "cases": cases})


if __name__ == "__main__":
    build()
