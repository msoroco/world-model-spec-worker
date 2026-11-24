"""Run exact offline and compatibility proofs for the partial six-case bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    run = subprocess.run(args, cwd=REPO, env=os.environ, capture_output=True,
                         text=True, timeout=300)
    log.write_text(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError("pinned CPU proof failed: " + str(log))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--validator", required=True, type=Path)
    args = parser.parse_args()
    scratch = (REPO / ".runtime-work").resolve()
    output = args.output_root.resolve()
    runtime_output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
    if (not output.is_relative_to(scratch) or
            not runtime_output.is_relative_to(scratch) or output.exists()):
        raise ValueError("fresh proof output and runtime root must be under .runtime-work")
    if not args.validator.is_file():
        raise ValueError("pinned Lean decoder absent")
    manifest = json.loads(MANIFEST.read_text())
    expected = {ROOT.name + "__" + name for name in REQUESTS}
    if {entry["case_id"] for entry in manifest["cases"]} != expected:
        raise ValueError("six exact parking case IDs required")
    output.mkdir(parents=True)
    for entry in manifest["cases"]:
        kind = entry["case_id"].removeprefix(ROOT.name + "__")
        folder = ROOT / "diagnostic" / kind
        for candidate_id, selected in (("primary", entry),
                                       ("fallback1", entry["candidates"][0])):
            construction = ROOT / selected["construction"]
            if sha(construction) != selected["construction_sha256"]:
                raise ValueError("selected construction changed")
            source = json.loads(construction.read_text())
            names = {item["path"] for item in source["files"]}
            if source.get("source_kind") == "retained_reviewed_native_site_packet":
                if "reviewed-context.json" in names or any(
                        name.startswith("reviewed_sources/") for name in names):
                    raise ValueError("reviewed sources must be supplied by source-hashed fixture")
                config = json.loads(next(item["content"] for item in source["files"]
                                         if item["path"] == "config.json"))
                packet_hash = config["reviewed_source_packet"]["sha256"]
                scene = json.loads(next(item["content"] for item in source["files"]
                                        if item["path"] == "scene.json"))
                recipe = json.loads((REPO / entry["fixture_recipe"]).read_text())
                packet_source = next((row for row in recipe["sources"]
                                      if row["path"] == "reviewed-context.json"), None)
                if (scene.get("source_packet_sha256") != packet_hash or
                        packet_source is None or packet_source["sha256"] != packet_hash or
                        sha(REPO / packet_source["source"]) != packet_hash):
                    raise ValueError("reviewed delivery fixture packet differs from scene")
            elif "reviewed-context.json" in names or any(
                    name.startswith("reviewed_sources/") for name in names):
                raise ValueError("delivery construction embeds diagnostic reviewed sources")
            proof = output / kind / candidate_id
            offline = proof / "offline"
            offline_log = folder / ("cpu-delivery-" + candidate_id + "-offline.log")
            offline_command = [sys.executable, str(REPO / "runtime.py"), "offline",
                               "--manifest", str(MANIFEST), "--case", entry["case_id"],
                               "--candidate", candidate_id, "--output", str(offline)]
            command(offline_command, offline_log)
            offline_receipt = json.loads(offline_log.read_text())
            if offline_receipt.get("offline_passed") is not True or offline_receipt.get("simulation_started") is not False:
                raise ValueError("offline source-bound construction proof differs")
            selected["offline"] = {"command": " ".join(offline_command),
                                   "exit_code": 0,
                                   "construction_sha256": selected["construction_sha256"],
                                   "log": offline_log.relative_to(ROOT).as_posix(),
                                   "log_sha256": sha(offline_log),
                                   "runtime_offline_log_sha256": sha(offline / "offline.log")}
            compat = proof / "compatibility"
            compat_log = folder / ("cpu-delivery-" + candidate_id + "-compat-command.log")
            compat_command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                              "--manifest", str(MANIFEST), "--case", entry["case_id"],
                              "--candidate", candidate_id, "--output", str(compat),
                              "--library", str(REPO / "runtime/library"),
                              "--validator", str(args.validator.resolve())]
            command(compat_command, compat_log)
            receipt = json.loads((compat / "compatibility.json").read_text())
            if (receipt.get("passed") is not True or
                    receipt.get("construction_sha256") != selected["construction_sha256"] or
                    receipt.get("scope") != "diagnostic software compatibility only"):
                raise ValueError("compatibility receipt does not bind selected construction")
            prefix = "cpu-delivery-" + candidate_id + "-"
            copied = {}
            for source_name, name in (("compatibility.json", "compatibility.json"),
                                      ("compatibility-analysis.log", "compatibility-analysis.log"),
                                      ("negative-analysis.log", "negative-analysis.log")):
                destination = folder / (prefix + name)
                shutil.copy2(compat / source_name, destination)
                copied[source_name] = destination
            selected["compatibility"] = {
                "receipt": copied["compatibility.json"].relative_to(ROOT).as_posix(),
                "sha256": sha(copied["compatibility.json"]),
                "log": copied["compatibility-analysis.log"].relative_to(ROOT).as_posix(),
                "negative_log": copied["negative-analysis.log"].relative_to(ROOT).as_posix()}
            if candidate_id == "primary":
                entry["negative"] = {"log": selected["compatibility"]["negative_log"],
                                     "sha256": sha(copied["negative-analysis.log"])}
            print(kind, candidate_id, "offline and compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
