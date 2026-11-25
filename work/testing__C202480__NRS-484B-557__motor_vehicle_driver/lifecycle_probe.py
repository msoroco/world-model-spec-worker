"""Exercise source-seal, native exit, owner release and saved closure order."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    root = args.fixture
    seal = seal_capture(root, frames=900, restoration={"restored": True},
                        errors=[], encoder_exit_codes={name: 0 for name in
                                                       ("overview", "approach", "reference_corner",
                                                        "driver_reference")},
                        context={"case_id": json.loads((root / "config.json").read_text())["selected_case_id"]})
    exit_record = record_native_exit(root)
    owner_path = root / "owner-release.json"
    owner = acknowledge_owner_release(root, owner_path, True)
    _closure(root, owner_path, "native", False)
    events = seal["events"] + [exit_record["event"], owner["event"],
                                "saved_processing_started"]
    args.output.write_text(json.dumps({"events": events, "exit_code": 0}, indent=2) + "\n")
    print(",".join(events))


if __name__ == "__main__":
    main()
