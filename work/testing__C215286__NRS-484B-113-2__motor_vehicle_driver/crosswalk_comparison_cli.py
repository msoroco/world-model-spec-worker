"""Run the independent crosswalk comparison on two saved source trees."""
import argparse
import json
from pathlib import Path

from comparison_audit import audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive", required=True)
    parser.add_argument("--stop-before", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.positive, args.stop_before), indent=2) + "\n")
