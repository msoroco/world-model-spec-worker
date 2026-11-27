"""Run the independent source-bound delivery audit after saved processing."""
import argparse
import json
from delivery_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    from pathlib import Path
    config = json.loads((Path(args.attempt)/"config.json").read_text())
    if config.get("selected_case_id") != args.case:
        raise ValueError("delivery audit exact case differs")
    print(json.dumps(audit(args.attempt), sort_keys=True))


if __name__ == "__main__":
    main()
