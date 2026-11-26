"""Exercise source-joined driveway outcomes and saved-stage closure on CPU."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import analysis


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def make_attempt(folder: Path, construction: dict, sources: dict, kind: str) -> None:
    folder.mkdir()
    for item in construction["files"]:
        target = folder / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    write(folder / "construction.json", construction)
    for name in ("original-attempt/reviewed-context.json",
                 "original-attempt/body-control-trace.jsonl",
                 "original-attempt/capture-receipt.json", "road.xodr",
                 "trace.jsonl", "video_frames.jsonl", "fixture-provenance.json"):
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sources[name])
    if kind == "missing_evidence":
        (folder / "original-attempt/reviewed-context.json").unlink()
        return
    if kind == "incomplete_motion":
        context = json.loads((folder / "original-attempt/reviewed-context.json").read_text())
        mouth_x = context["mouth_start_xy"][0]
        target_x = mouth_x if context["observed_conditions"]["position_target"] == "outside_5ft" else mouth_x + 10
        vertices = [[x, y, z] for x in (target_x - 1, target_x + 1)
                    for y in (1.0, 2.0) for z in (0.0, 1.5)]
        trace = folder / "original-attempt/body-control-trace.jsonl"
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        for row in rows:
            row["vehicle_vertices"] = vertices
        trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        receipt_path = folder / "original-attempt/capture-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["trace_sha256"] = sha(trace)
        write(receipt_path, receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", default=str(ROOT / "execution-manifest.draft.json"))
    args = parser.parse_args()
    from worker_exchange.common import read
    from worker_exchange.native_output import validate_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources

    manifest = Path(args.manifest).resolve()
    entry = next(row for row in read(manifest)["cases"] if row["case_id"] == args.case)
    construction = read(ROOT / entry["construction"])
    embedded = next(item["content"] for item in construction["files"] if item["path"] == "analysis.py")
    if hashlib.sha256(embedded.encode()).hexdigest() != sha(ROOT / "analysis.py"):
        raise ValueError("physical probe analyzer differs from exact construction")
    slug = args.case.removeprefix(ROOT.name + "__")
    sources = read(ROOT / "diagnostics" / slug / "diagnostic.json")["files"]
    output = Path(args.output).resolve()
    if REPO / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("fresh physical fixture output under .runtime-work required")
    output.mkdir(parents=True)
    command = ("SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c229404-owner-nov26 "
               "PYTHONPATH=runtime/scenario_pipeline:runtime/python .venv-cpu/bin/python "
               f"work/{ROOT.name}/physical_probe.py --case {args.case} "
               f"--output {args.output} --manifest {args.manifest}")
    fixtures = []
    positive = None
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        attempt = output / kind
        make_attempt(attempt, construction, sources, kind)
        if kind == "missing_evidence":
            try:
                analysis.build(attempt)
            except ValueError as error:
                if "Missing required source: original-attempt/reviewed-context.json" not in str(error):
                    raise
                result = copy.deepcopy(positive)
                result.update(measured_values={}, setup_confirmed=False,
                              behavior_attempted=False, maneuver_completed=False,
                              realized_observables={},
                              termination_reason="Selected reviewed context missing")
                for check in result["physical_checks"].values():
                    check.update(status="unverified", method="selected analyzer rejected missing source",
                                 missing_evidence=[str(error)])
                log_text = str(error)
            else:
                raise ValueError("missing selected source was accepted")
        else:
            report, measurement, frames = analysis.build(attempt)
            result = analysis.save_result(attempt, report, measurement, frames)
            log_text = (f"{kind}: {measurement['activity_window']['frame_count']} synthetic "
                        f"source-joined activity frames; target {result['target_checks'][0]['matched']}")
            if kind == "complete_motion":
                positive = result
        validate_result(result)
        if (result["physical_checks"]["maneuver"]["status"] != expected or
                result["maneuver_completed"] != (expected == "met") or
                result.get("diagnostic_fixture") is not True or
                result.get("provenance_kind") != "synthetic_fixture"):
            raise ValueError("synthetic physical outcome differs: " + kind)
        result_path = ROOT / f"physical-{slug}-{kind}.json"
        log_path = ROOT / f"physical-{slug}-{kind}.log"
        write(result_path, result)
        log_path.write_text(log_text.rstrip() + "\n")
        fixtures.append({"kind": kind, "command": command,
                         "exit_code": 0, "log": log_path.name,
                         "log_sha256": sha(log_path), "result": result_path.name,
                         "result_sha256": sha(result_path)})
    complete = output / "complete_motion"
    seal_capture(complete, frames=9,
                 restoration={"restored": True, "settings_readback": "synthetic protocol"},
                 errors=[], encoder_exit_codes={"synthetic": 0})
    native_exit = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = output / "saved-stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if (not native_exit["capture_seal_sha256"] or not owner["native_exit_sha256"]
            or not (stage / "original-attempt/reviewed-context.json").is_file()):
        raise ValueError("synthetic saved-stage lifecycle did not close")
    life_path = ROOT / f"physical-{slug}-lifecycle.log"
    life_path.write_text("capture_finished\nencoders_closed\nrestoration_verified\n"
                         "native_exit\nowner_released\nsaved_processing_started\n")
    proof_path = ROOT / f"physical-{slug}-proof.json"
    write(proof_path, {"case_id": args.case,
                       "construction_sha256": entry["construction_sha256"],
                       "fixtures": fixtures,
                       "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                                "restoration_verified", "native_exit",
                                                "owner_released", "saved_processing_started"],
                                     "exit_code": 0, "log": life_path.name,
                                     "log_sha256": sha(life_path)}})
    print(json.dumps({"case_id": args.case, "physical_proof": proof_path.name,
                      "outcomes": [f["kind"] for f in fixtures],
                      "synthetic_only": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
