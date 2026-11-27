"""Write one exact source-bound measurement contract per selected case."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = ["night-parking-sources.json", "context.json", "classification.json", "activity.json", "trace.jsonl", "video_frames.jsonl"]


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    disposition = plan["requirement_dispositions"][0]
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[1]
        path = ROOT / "cases" / suffix / "measurement-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        contract = {
            "format": "worker-measurement-contract",
            "requirements": [{
                "disposition_index": 0,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": "nighttime_parking_episode",
                "method": "measure_night_parking",
                "value_type": "object",
                "kind": "measured",
                "inputs": INPUTS,
            }],
            "negative": {"remove": ["classification.json"],
                         "error_contains": "Missing required source: classification.json"},
        }
        path.write_text(json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    main()
