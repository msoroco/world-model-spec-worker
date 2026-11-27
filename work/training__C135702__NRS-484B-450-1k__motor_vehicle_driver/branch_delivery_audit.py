"""Independent obstruction audit plus original police-source branch gate."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "native"))
import delivery_audit
from branch_runner import PREFIX, reviewed_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--operations")
    parser.add_argument("--output")
    parser.add_argument("--trace", default="converted/trace.json")
    parser.add_argument("--video", default="primary.mkv")
    parser.add_argument("--review", default="obstruction-review.json")
    parser.add_argument("--job", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    args = parser.parse_args()
    if args.case not in (PREFIX + "police_absent", PREFIX + "police_present"):
        raise ValueError("Exact police-source branch case required")
    if args.self_test:
        print(json.dumps(delivery_audit.selftest(args.case, args.negative)))
        return
    context = Path(args.attempt) / "exception-context.json"
    reviewed_context(context, args.case)
    result = delivery_audit.audit(args)
    result["police_source_gate_sha256"] = delivery_audit.sha(context)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
