"""Build original-source packets and run the independent pair audit."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from comparison_audit import audit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packet(attempt, output):
    attempt = Path(attempt)
    value = {"context": json.loads((attempt/"median-context.json").read_text()),
             "samples": [json.loads(line) for line in (attempt/"ego-body-history.jsonl").read_text().splitlines()],
             "provenance_kind": "native", "diagnostic_fixture": False}
    output.write_text(json.dumps(value, sort_keys=True)+"\n")
    return output, sha(output), attempt/"config.json", sha(attempt/"config.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not root.is_relative_to(repo/".runtime-work"):
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix="c80909-comparison-audit-") as scratch:
        temp = Path(scratch)
        lp,lh,lc,lch = packet(args.left,temp/"left.json")
        rp,rh,rc,rch = packet(args.right,temp/"right.json")
        print(json.dumps(audit(args.comparison,lp,lh,rp,rh,lc,lch,rc,rch),sort_keys=True))


if __name__ == "__main__":
    main()
