"""Source-bound CPU proof of launch control and observed timing separation."""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from traffic_timing_sweep import TrafficLaunch, measure
from traffic_timing_sweep_runner import check as runner_check
from traffic_timing_sweep_finalize import finalize as finalize_sweep


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def reject(call):
    try:
        call()
    except ValueError as error:
        return str(error)
    raise AssertionError("Damaged physical sweep source was accepted")


def main():
    manifest_path = HERE / "update038-ten-case-probe-manifest.json"
    index_path = HERE / "update038-ten-case-matrix-index.json"
    manifest, index = read(manifest_path), read(index_path)
    require(index["manifest_sha256"] == sha(manifest_path) and
            index["candidates"] == 40, "Current final-hash matrix missing")
    plan = TrafficLaunch(30)
    require(plan.command(29)["brake"] == 1.0 and
            plan.command(30)["throttle"] == .25 and
            plan.command(260)["throttle"] == .25 and
            plan.command(261)["hand_brake"] is True,
            "Traffic timing control boundaries differ")
    outputs = []
    for suffix in ("traffic_yield_wait", "traffic_conflict_entry"):
        case_id = HERE.name + "__" + suffix
        construction = next(entry for entry in manifest["cases"]
                            if entry["case_id"] == case_id)
        require(sha(HERE / construction["construction"]) ==
                construction["construction_sha256"],
                "Exact construction changed")
        if suffix == "traffic_yield_wait":
            config_text = next(file["content"] for file in
                               read(HERE / construction["construction"])["files"]
                               if file["path"] == "config.json")
            sweep_config = json.loads(config_text)
            sweep_config.update(case_id=HERE.name + "__C110919-right-of-way-0000",
                                sweep_id="C110919-right-of-way",
                                traffic_launch_frame=30)
            static = runner_check(sweep_config)
            require(static["native_imported"] is False and
                    static["physical_success_claimed"] is False,
                    "Sweep runner made physical claim during static check")
        run = ROOT / ".runtime-work/c110919-update038-ten-case-matrix" / sha(manifest_path)[:12] / suffix / "primary"
        attempt = run / "compatibility"
        saved_path = run / "saved/v0001/processing.json"
        saved = read(saved_path)
        source_path = attempt / "native_samples.jsonl"
        require(saved["passed"] is True and
                saved["original_source_hashes"]["native_samples.jsonl"] == sha(source_path) and
                saved["physical_acceptance_claimed"] is False and
                saved["legal_acceptance_claimed"] is False,
                "Retained Native-shaped source or saved receipt changed")
        rows = [json.loads(line) for line in source_path.read_text().splitlines()]
        require(all(row.get("synthetic_diagnostic") is True for row in rows),
                "Diagnostic provenance changed")
        measured = measure(rows, launch_frame=30)
        require(measured["observed_traffic_first_frame"] == 220 and
                measured["observed_traffic_last_frame"] == 260 and
                measured["legal_right_of_way_verdict"] is None,
                "Observed traffic timing or legal neutrality changed")
        outputs.append({"case_id": case_id, "source_sha256": sha(source_path),
                        "saved_receipt_sha256": sha(saved_path), "measurement": measured})
    negatives = {}
    sample = [json.loads(line) for line in (
        ROOT / ".runtime-work/c110919-update038-ten-case-matrix" / sha(manifest_path)[:12] /
        "traffic_yield_wait/primary/compatibility/native_samples.jsonl"
    ).read_text().splitlines()]
    changed = copy.deepcopy(sample)
    changed[240]["traffic_conflict_occupied"] = False
    negatives["altered_occupancy"] = reject(lambda: measure(changed, launch_frame=30))
    changed = copy.deepcopy(sample)
    changed[240]["other_traffic_signal_state_observed"] = "Red"
    negatives["altered_signal"] = reject(lambda: measure(changed, launch_frame=30))
    changed = copy.deepcopy(sample)
    changed[240]["time_s"] += 1
    negatives["altered_time"] = reject(lambda: measure(changed, launch_frame=30))
    negatives["unsupported_launch"] = reject(lambda: TrafficLaunch(260))
    finalizer_attempt = ROOT / ".runtime-work/c110919-update048-finalizer/compatibility"
    finalizer_report = read(finalizer_attempt / "analysis-report.json")
    finalizer_result = read(finalizer_attempt / "result.json")
    require(finalizer_report["case_id"] == "C110919-right-of-way-0000" and
            finalizer_report["measurements"]["traffic_timing_sweep"]["value"]["ego_minus_traffic_entry_s"] == 2.9 and
            finalizer_result["measured_values"]["traffic_timing_sweep"]["legal_right_of_way_verdict"] is None and
            finalizer_result["provenance_kind"] == "synthetic_local_diagnostic" and
            finalizer_result["accepted"] is False and
            finalizer_result["legal_verdict_claimed"] is False and
            set(finalizer_report["video_frames"].values()) == {480},
            "Saved-only sweep finalizer diagnostic or provenance differs")
    with tempfile.TemporaryDirectory(prefix="c110919-sweep-negative-", dir=ROOT / ".runtime-work") as folder:
        damaged = Path(folder)
        for child in finalizer_attempt.iterdir():
            if child.name in ("config.json", "result.json", "analysis-report.json", "channels", "context"):
                continue
            (damaged / child.name).symlink_to(child)
        wrong = read(finalizer_attempt / "config.json")
        wrong["traffic_launch_frame"] = 31
        (damaged / "config.json").write_text(json.dumps(wrong) + "\n")
        negatives["selected_launch_differs_from_raw"] = reject(
            lambda: finalize_sweep(damaged, damaged / "analysis-report.json"))
    proof = {"format": "c110919-traffic-timing-sweep-control-cpu-proof-v1",
             "manifest_sha256": sha(manifest_path),
             "historical_manifest_case_plan_sha256": manifest["case_plan_sha256"],
             "current_case_plan_sha256": sha(HERE / "case-plan.json"),
             "matrix_index_sha256": sha(index_path),
             "control_source_sha256": sha(HERE / "native/traffic_timing_sweep.py"),
             "runner_source_sha256": sha(HERE / "native/traffic_timing_sweep_runner.py"),
             "finalizer_source_sha256": sha(HERE / "native/traffic_timing_sweep_finalize.py"),
             "saved_only_finalizer_probe": {
                 "report_sha256": sha(finalizer_attempt / "analysis-report.json"),
                 "result_sha256": sha(finalizer_attempt / "result.json"),
                 "synthetic_source_sha256": sha(finalizer_attempt / "native_samples.jsonl"),
                 "video_frames_checked": 480,
                 "original_native_accepted": False},
             "outcomes": outputs, "negative_rejections": negatives,
             "sweep_spec_complete": False, "original_native_accepted": False,
             "legal_verdict_claimed": False}
    target = HERE / "update040-traffic-timing-sweep-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"source_bound_cases": 2, "negative_rejections": len(negatives),
                      "proof_sha256": sha(target), "sweep_spec_complete": False}))


if __name__ == "__main__":
    main()
