"""Exercise exact source audit on a marked synthetic CPU fixture."""

import argparse
from pathlib import Path

from delivery_audit import audit_saved


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if not args.case.startswith(PACKAGE.name + "__"):
        raise ValueError("exact assignment case required")
    suffix = args.case.removeprefix(PACKAGE.name + "__")
    attempt = ROOT / ".runtime-work/c229813-owner/compat-all-v2" / (suffix + "-primary")
    result = audit_saved(attempt, args.case, diagnostic=not args.negative)
    if result["frame_count"] != 9 or not result["checks"]["time_join"] or \
            not result["checks"]["full_video_decode"] or result["checks"]["native_source"]:
        raise ValueError("synthetic CPU source audit is incomplete or misclassified")
    print("synthetic CPU source audit passed:", args.case)
    print("Original pixels, physical completion and legal outcome remain unverified")


if __name__ == "__main__":
    main()
