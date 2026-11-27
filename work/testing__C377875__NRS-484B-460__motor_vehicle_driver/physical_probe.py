"""CPU-only physical-completion and lifecycle fixtures for angle parking."""
import argparse
import json
import shutil
from pathlib import Path

from worker_exchange.native_output import assess_physical, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + "\n")


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def probe(case_id, source, output, kind):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("retain prior CPU probe")
    output.mkdir(parents=True)
    for name in ("config.json", "trace.jsonl", "video_frames.jsonl", "angle-history.jsonl",
                 "fixture-provenance.json"):
        shutil.copy2(source / name, output / name)
    cfg = json.loads((output / "config.json").read_text())
    if cfg.get("selected_case_id") != case_id:
        raise ValueError("probe selects another exact case")
    if kind == "incomplete_motion":
        history = rows(output / "angle-history.jsonl")
        origin = history[0]["position_xy"]
        for event in history:
            event["position_xy"] = [origin[0] + .01 * event["sample_index"], origin[1]]
        (output / "angle-history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in history))
    elif kind == "missing_evidence":
        (output / "angle-history.jsonl").unlink()
    elif kind == "lifecycle":
        for name in ("construction.json", "runner.py", "acquisition-provenance.json"):
            if (source / name).exists():
                shutil.copy2(source / name, output / name)
        if not (output / "acquisition-provenance.json").exists():
            write(output / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        seal_capture(output, frames=len(rows(output / "trace.jsonl")),
                     restoration={"restored": True, "settings_readback": "CPU fixture"},
                     errors=[], encoder_exit_codes={"diagnostic": 0})
        native_exit = record_native_exit(output)
        owner = acknowledge_owner_release(output, output / "owner-release.json", True)
        stage = output / "saved-stage"
        stage.mkdir()
        copy_sources(output, stage)
        if owner["native_exit_sha256"] != native_exit["capture_seal_sha256"] and not (stage / "capture-seal.json").is_file():
            raise ValueError("CPU lifecycle source copy failed")
        value = {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                            "native_exit", "owner_released", "saved_processing_started"],
                 "diagnostic_fixture": True}
        write(output / "physical-result.json", value)
        return value
    elif kind != "complete_motion":
        raise ValueError("unsupported CPU physical fixture")
    result = assess_physical(output, cfg, [])
    result["provenance_kind"] = "synthetic_fixture"
    result["diagnostic_fixture"] = True
    write(output / "physical-result.json", result)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if result["physical_checks"]["maneuver"]["status"] != expected:
        raise ValueError("CPU physical fixture status differs: " + kind)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kind", required=True)
    args = parser.parse_args()
    result = probe(args.case, args.source, args.output, args.kind)
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status"),
                      "events": result.get("events")}))


if __name__ == "__main__":
    main()
