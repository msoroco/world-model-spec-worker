"""Report saved-only processing feedback without requesting a Native replay."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    versions = sorted(Path(args.output).glob("v[0-9][0-9][0-9][0-9]"))
    if not versions:
        raise SystemExit("No saved-processing version exists")
    version = versions[-1]
    source = version / "feedback.json"
    if not source.is_file():
        source = version / "processing.json"
    if not source.is_file():
        raise SystemExit("Saved-processing feedback is missing")
    result = json.loads(source.read_text())
    if result.get("recorded_only") is not True:
        raise SystemExit("Saved-processing result is not recorded-only")
    print(json.dumps({"recorded_only": True, "native_replay_requested": False,
                      "version": str(version), "feedback": result}, sort_keys=True))


if __name__ == "__main__":
    main()
