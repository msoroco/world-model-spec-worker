"""Bind current exact constructions for CARLA-free offline materialization."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for suffix, relative in (("a", "construction.json"),
                             ("b", "cases/condition_b/construction.json")):
        case_id = ASSIGNMENT + "__selected_dacdf461__condition_" + suffix
        fallback = "cases/condition_" + suffix + "/fallback1-construction.json"
        entries.append({"case_id": case_id, "kind": "delivery",
                        "construction": relative,
                        "construction_sha256": sha(ROOT / relative),
                        "candidate_risk": {"status": "physical",
                                           "reason": "Passing actor may not reach a stable pre-obstruction halt with the primary braking station."},
                        "candidates": [{"id": "fallback1", "construction": fallback,
                                        "construction_sha256": sha(ROOT / fallback),
                                        "trigger": {"source": "original native_samples.jsonl",
                                                    "metric": "minimum_passing_speed_m_s and passing_halt_frames",
                                                    "failure_condition": "condition_a has fewer than 20 source halt frames before the obstruction"},
                                        "changed_knobs": ["passing_throttle .25 to .35",
                                                          "brake_station_x_m -11 to -15"]}]})
    value = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
             "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
             "status": "offline_draft_only", "cases": entries}
    (ROOT / "draft-execution-manifest.json").write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    build()
