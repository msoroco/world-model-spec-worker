"""Materialized exact-case entrypoint for offline checking and local Native use."""
import argparse
import json
import os
from pathlib import Path

from capture_runner import check_config, execute, require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check_config(config), sort_keys=True))
        return
    require(args.output_dir, "Native attempt output required")
    survey_path = args.site_survey or os.environ.get("SCENARIO_EMERGENCY_SITE_SURVEY")
    require(survey_path, "Original same-cell emergency site survey required")
    survey = json.loads(Path(survey_path).read_text())
    execute(config, survey, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
