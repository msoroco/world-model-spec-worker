"""Bind current exact-case CPU proofs into the selected delivery manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    draft = read(HERE / "draft-native-manifest.json")
    entries = []
    for i, source in enumerate(draft["cases"], 1):
        suffix = f"controlled_{i}"
        entry = dict(source, kind="delivery", status="selected_cpu_prepared")
        entry.pop("recording_description", None)
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Original facility boundary may be too small or obscured in world-camera pixels; require measurable visible-pixel check before camera shift."}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        for candidate_id, target in (("primary", entry),
                                     ("fallback1", entry["candidates"][0])):
            stem = f"selected-{suffix}-{candidate_id}"
            target["offline"] = {
                "exit_code": 0,
                "construction_sha256": target["construction_sha256"],
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/draft-native-manifest.json --case {entry['case_id']} --candidate {candidate_id} --output .runtime-work/c111250-final-{i}-{candidate_id}-offline",
                "log": stem + "-offline.log",
                "log_sha256": sha(HERE / (stem + "-offline.log"))}
            target["compatibility"] = {
                "receipt": stem + "-compatibility.json",
                "sha256": sha(HERE / (stem + "-compatibility.json")),
                "log": stem + "-analysis.log",
                "negative_log": stem + "-negative.log"}
        entry["negative"] = {"log": f"selected-{suffix}-primary-negative.log"}
        entry["physical_preparation"] = {
            "receipt": f"physical-{suffix}-proof.json",
            "sha256": sha(HERE / f"physical-{suffix}-proof.json")}
        channels = read(HERE / entry["construction"])["recording_description"]["channels"]
        entry["acquisition"] = {
            channel["name"]: {"entrypoint": "finalize.py",
                              "method": "20 Hz original source-bound body/map/trace measurement",
                              "evidence": "channels/" + channel["name"] + ".jsonl"}
            for channel in channels}
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry['case_id']} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $ADAPTER_CHECK",
            "feedback_command": f".venv-cpu/bin/python work/{HERE.name}/audit-selected-delivery.py --case {entry['case_id']}",
            "test_exit_code": 0,
            "test_log": f"selected-{suffix}-primary-processing.json",
            "test_log_sha256": sha(HERE / f"selected-{suffix}-primary-processing.json")}
        receipt_path = HERE / f"delivery-{suffix}-acceptance.json"
        if receipt_path.is_file():
            entry["delivery_acceptance"] = read(receipt_path)
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "selected_cpu_prepared", "cases": entries}
    path = HERE / "execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest": sha(path), "cases": len(entries)}))


if __name__ == "__main__":
    main()
