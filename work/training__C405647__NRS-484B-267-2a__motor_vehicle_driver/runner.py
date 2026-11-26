"""Dispatch an exact selected Native construction from the four-case package."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    manifest = json.loads((folder / "execution-manifest.json").read_text())
    matches = [entry for entry in manifest["cases"] if entry["case_id"] == args.case]
    if len(matches) != 1:
        raise ValueError("Exact selected case is absent from the execution manifest")
    entry = matches[0]
    construction = json.loads((folder / entry["construction"]).read_text())
    if construction["case_id"] != args.case:
        raise ValueError("Selected construction case differs")
    if not args.check and not args.output_dir:
        raise ValueError("Native attempt output required")
    scratch = folder.parents[1] / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c405647-dispatch-", dir=scratch) as temporary:
        bundle = Path(temporary)
        for item in construction["files"]:
            path = bundle / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["content"])
        command = [sys.executable, "-B", "runner.py"]
        if args.check:
            command.append("--check")
        else:
            command.extend(("--output-dir", str(Path(args.output_dir).resolve()),
                            "--host", args.host, "--port", str(args.port)))
            if args.site_survey:
                command.extend(("--site-survey", args.site_survey))
        subprocess.run(command, cwd=bundle, check=True)


if __name__ == "__main__":
    main()
