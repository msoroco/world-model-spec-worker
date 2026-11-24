"""Derive a shared reciprocal fallback from each exact primary inline bundle."""

import hashlib
import json
from pathlib import Path

from reciprocal_fallback import CASES, TRIGGER

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate():
    for case_id in CASES:
        suffix = case_id.rsplit("__", 1)[-1]
        source = ROOT / "cases" / suffix / "construction.json"
        bundle = json.loads(source.read_text(encoding="utf-8"))
        config = next(item for item in bundle["files"] if item["path"] == "config.json")
        configuration = json.loads(config["content"])
        configuration["controller"]["target_speed_mps"] = 3.0
        configuration["candidate_id"] = "fallback1"
        config["content"] = json.dumps(configuration, indent=2) + "\n"
        runner = next(item for item in bundle["files"] if item["path"] == "runner.py")
        original = '    if request["controller"] != policy:\n'
        if runner["content"].count(original) != 1:
            raise ValueError("primary runner contract changed")
        runner["content"] = runner["content"].replace(
            original,
            '    if config.get("candidate_id") == "fallback1":\n'
            '        request["controller"]["target_speed_mps"] = 3.0\n' + original)
        runner_source = ROOT / (suffix + "_fallback_bundle_runner.py")
        runner_source.write_text(runner["content"], encoding="utf-8")
        runner["source"] = str(runner_source.relative_to(ROOT.parents[1]))
        bundle["source_kind"] = "diagnostic_offline_reciprocal_fallback_native_review_required"
        target = ROOT / "cases" / suffix / "fallback1-construction.json"
        write(target, bundle)
        print(suffix, sha(target))


if __name__ == "__main__":
    generate()
