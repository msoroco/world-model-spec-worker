"""Selected case finalizer with explicit diagnostic and original branches.

Diagnostic rows establish only software compatibility. Original source
measurements require the sealed rider, pedestrian, emitter and microphone data.
"""

import argparse
import json
from pathlib import Path

import diagnostic_analysis
import production_analysis


def measure_case(attempt):
    root = Path(attempt)
    marker = root / "diagnostic-source-note.json"
    if marker.is_file():
        note = json.loads(marker.read_text())
        if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
                note.get("accepted_original_source") is not False):
            raise ValueError("diagnostic source identity differs")
        report = diagnostic_analysis.analyze(root)
        report["measurements"]["sidewalk_overtake_signal"]["method"] = "measure_case"
        return report, None
    report, native = production_analysis.build(root)
    report["measurements"]["sidewalk_overtake_signal"]["method"] = "measure_case"
    return report, native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior selected analysis")
    report, native = measure_case(args.attempt)
    if native is not None:
        from worker_exchange.native_output import write_result
        write_result(args.attempt, native)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
