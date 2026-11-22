"""Positive and tampered-source CPU probe of the independent delivery audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
from pathlib import Path

from delivery_audit import audit
from native_capture import CAMERA_SPECS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE/"execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    tokens = shlex.split(entry["compatibility"]["command"])
    source = (REPO/tokens[tokens.index("--output")+1]).resolve()
    output = Path(args.output).resolve()
    if (not source.is_relative_to(REPO/".runtime-work") or
            not output.is_relative_to(REPO/".runtime-work") or output.exists()):
        raise ValueError("fresh diagnostic audit directory under .runtime-work required")
    output.mkdir(parents=True)
    names = ("scene.json", "candidate-corridor.xodr", "trace.jsonl",
             "walker-body-history.jsonl", "video_frames.jsonl",
             "camera-frame-joins.jsonl", "analysis-report.json", "result.json",
             "acquisition-provenance.json", *(name+".mkv" for name in CAMERA_SPECS))
    for name in names:
        shutil.copyfile(source/name, output/name)
    sources = {name: sha(output/name) for name in names}
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    seal = {"format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "frames": len((output/"video_frames.jsonl").read_text().splitlines()),
            "restoration": {"restored": True}, "sources": sources,
            "source_digest": digest, "physical_acceptance_claimed": False}
    (output/"capture-seal.json").write_text(json.dumps(seal, indent=2)+"\n")
    if args.negative:
        with (output/"walker-body-history.jsonl").open("a") as stream:
            stream.write("\n")
    receipt = audit(output, diagnostic_test=True)
    if (not receipt["diagnostic_audit_test_passed"] or
            not receipt["full_video_decode_passed"] or
            receipt["physical_acceptance_claimed"] or
            receipt["actual_pixel_visibility_verified"]):
        raise AssertionError("diagnostic audit made an unsupported claim")
    print(json.dumps({"case_id": args.case, "diagnostic_audit_test_passed": True,
                      "four_actual_video_byte_streams_decoded": True,
                      "walker_visibility_claimed": False,
                      "physical_completion_status": receipt["physical_completion_status"]},
                     indent=2))


if __name__ == "__main__":
    main()
