"""Materialize three exact source-gated alley Native CPU bundles."""
import hashlib
import json
from pathlib import Path

from selected_plan import CASES


PACKAGE = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    config = json.loads((HERE / "selected-config.json").read_text())
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": PACKAGE.name,
                "runtime_manifest_sha256": sha(Path("runtime/SOURCE-MANIFEST.json")),
                "delivery_ready": False, "status": "selected_cpu_proofs_pending",
                "cases": []}
    for case_id in CASES:
        suffix = case_id.rsplit("__", 1)[-1]
        destination = PACKAGE / "native-selected" / suffix
        selected = dict(config, selected_case_id=case_id,
                        case={"case_id": case_id},
                        requested_goods_motion=CASES[case_id]["goods_motion_requested"],
                        requested_idle_after_goods=CASES[case_id]["idle_after_goods_requested"],
                        requested_goods_motion_frame=CASES[case_id]["goods_motion_frame"])
        write(destination / "config.json", selected)
        sources = {
            "runner.py": HERE / "selected_runner.py",
            "selected_plan.py": HERE / "selected_plan.py",
            "selected_finalize.py": HERE / "selected_finalize.py",
            "tests/test_selected_plan.py": HERE / "tests/test_selected_plan.py",
            "tests/test_runner.py": HERE / "tests/test_selected_runner.py",
            "tests/test_selected_finalize.py": HERE / "tests/test_selected_finalize.py",
        }
        for relative, source in sources.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text())
        files = [{"path": relative,
                  "content": (destination / relative).read_text()}
                 for relative in ("config.json", *sources)]
        construction = {
            "case_id": case_id, "law_id": "NRS-484B-477-1a",
            "cell_id": "C378809", "actor": "motor_vehicle_driver",
            "entrypoint": "runner.py", "files": files,
            "recording_description": {
                "channels": [{"name": name, "unit": "source observation",
                              "method": "saved original Native and source review join",
                              "reference_frame": "surveyed alley and goods source frames",
                              "sampling_rate_hz": 20, "time_window": "600 frames / 30 s",
                              "uncertainty": "Original alley, district, ordinance and goods source review required"}
                             for name in ("kin.position", "kin.speed", "st.alley",
                                          "drv.standing_or_parked", "kin.time",
                                          "kin.extent", "sig.door_open",
                                          "ru.commercial_motor_vehicle",
                                          "st.driveway_or_alley_entrance", "rel.occupies")],
                "context_inputs": ["original alley survey", "local ordinance review"],
                "limitations": ["Scripted goods motion is not original transfer evidence",
                                "Expeditiousness and ordinance status remain independent judgment"]},
            "measurement_plan": {"method": "source_join_measurement",
                                 "entrypoint": "selected_finalize.py"},
            "static_checks": ["source-gated alley/district/ordinance/prop geometry",
                              "four camera names and dimensions", "20 Hz for 600 frames"],
            "termination_rules": ["600 synchronized frames", "owner release and restore"],
            "mechanisms": ["surveyed vehicle park request",
                           "source-aligned goods prop motion request"]}
        write(destination / "construction.json", construction)
        write(destination / "measurement-contract.json", {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{
                "disposition_index": 0, "requirement": "NRS-484B-477-1a",
                "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
                "output_key": "alley_goods_dwell_measurement",
                "method": "measure_alley", "value_type": "object",
                "kind": "measured",
                "inputs": ["site-survey.json", "goods-review.json",
                           "alley-native.jsonl", "video_frames.jsonl"]}],
            "negative": {"remove": ["goods-review.json"],
                         "error_contains": "Missing required source: goods-review.json"}})
        manifest["cases"].append({
            "case_id": case_id, "kind": "delivery",
            "construction": str((destination / "construction.json").relative_to(PACKAGE)),
            "construction_sha256": sha(destination / "construction.json"),
            "measurement_contract": str((destination / "measurement-contract.json").relative_to(PACKAGE)),
            "measurement_procedure": {"entrypoint": "selected_finalize.py"},
            "candidate_risk": {"status": "none", "reason": "No alternate geometry selected before source review"},
            "candidates": []})
    write(PACKAGE / "selected-draft-manifest.json", manifest)
    return {"cases": len(manifest["cases"]),
            "manifest_sha256": sha(PACKAGE / "selected-draft-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
