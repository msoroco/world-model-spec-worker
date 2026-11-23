"""Run the independent delivery audit for one named exact diagnostic case.

The attempt must already contain source decode receipts. This command never
claims that synthetic imagery establishes crossing feature visibility.
"""

import argparse
import json
from pathlib import Path

from delivery_audit import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt)
    if result["case_id"] != args.case:
        raise ValueError("delivery audit selected another case")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
