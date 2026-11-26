"""Exact-case dispatch preflight; selected Native runners own acquisition."""
import argparse
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def check(case):
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    config = json.loads((ROOT / "config.json").read_text())
    cases = {item["case_id"] for item in manifest["cases"]}
    if case not in cases or cases != set(config["supported_case_ids"]):
        raise ValueError("Select an exact prepared bus school-crossing case")
    return {"case_id": case, "frames": 600, "rate_hz": 20,
            "physical_acceptance_claimed": False}
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.case), sort_keys=True))
