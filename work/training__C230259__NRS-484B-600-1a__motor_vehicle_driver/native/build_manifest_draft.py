"""Bind exact-case CPU compatibility inputs for the selected speed sweep."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
AID = ROOT.name
SOURCES = ["native_motion.jsonl", "conditions.jsonl", "video_frames.jsonl",
           "trace.jsonl", "capture/evidence.jsonl", "road.xodr"]
KEYS = ["statutory_actor_context", "speed_conditions", "traffic_scope",
        "highway_conditions", "weather_conditions"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    entries = []
    for speed in (8, 12, 16, 20):
        case = AID + "__" + str(speed)
        construction = HERE / f"{speed}-construction.json"
        rows = []
        for index, (disposition, key) in enumerate(zip(plan["requirement_dispositions"], KEYS)):
            rows.append({"disposition_index": index, "requirement": disposition["requirement"],
                         "source": disposition["source"], "kind": "sourced_context" if index else "measured",
                         "method": "finalize", "output_key": key, "value_type": "object", "inputs": SOURCES})
        write(HERE / f"{speed}-measurement-contract.json",
              {"format": "worker-measurement-contract", "case_id": case,
               "requirements": rows, "status": "draft",
               "negative": {"remove": ["conditions.jsonl"],
                            "error_contains": "Missing required source: conditions.jsonl"}})
        entries.append({"case_id": case, "id": str(speed), "kind": "delivery",
                        "construction": f"native/{speed}-construction.json",
                        "construction_sha256": sha(construction),
                        "fixture_recipe": f"work/{AID}/native/diagnostic/{speed}/fixture-recipe.json",
                        "measurement_contract": f"native/{speed}-measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    write(ROOT / "execution-manifest.json",
          {"assignment_id": AID, "format": "worker-execution-manifest", "status": "draft",
           "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
           "cases": entries})


if __name__ == "__main__":
    main()
