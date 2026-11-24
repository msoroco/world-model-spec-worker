"""Map each retained exact observation to its Native or saved source implementation."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP = {
    "siren_active": ("device_readback.py", "external instrument siren boolean joined to each Native frame", "device_samples.jsonl and device_trace.jsonl"),
    "warning_lamp_active": ("device_readback.py", "external instrument lamp boolean joined to each Native frame", "device_samples.jsonl and device_trace.jsonl"),
    "ego_position": ("actor_readback.py", "ego.get_transform sampled for each Native frame", "actor_trace.jsonl ego source actor id and pose"),
    "pedestrian_position": ("actor_readback.py", "pedestrian.get_transform sampled for each Native frame", "actor_trace.jsonl pedestrian source actor id and pose"),
    "camera_frame_identity": ("camera_recorder.py", "four RGB sensor callbacks joined to each Native frame", "camera_trace.jsonl and four original ZIP sources"),
    "original_siren_and_warning_lamp_state": ("device_readback.py", "independent boolean samples and command/readback retained separately", "device_samples.jsonl and device_trace.jsonl"),
    "qualifying_event_and_temporal_relation": ("original_adapters.py", "sealed dispatch document joined to each original device frame by saved analysis", "dispatch_context.json and device_trace.jsonl"),
    "pedestrian_approach_relation": ("actor_readback.py", "two original actor poses joined by Native frame", "actor_trace.jsonl and camera_trace.jsonl"),
    "equipment_and_authorization": ("original_adapters.py", "reviewed equipment source retained and joined to each original frame", "equipment_record.json and device_trace.jsonl"),
}


def main() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        construction = json.loads((HERE / entry["construction"]).read_text())
        files = {item["path"]: item["content"] for item in construction["files"]}
        names = {item["name"] for item in construction["recording_description"]["channels"]}
        if names != set(MAP):
            raise ValueError("Exact observation channel set differs")
        acquisition = {}
        for name, (source, method, evidence) in MAP.items():
            if files.get(source) != (HERE / source).read_text():
                raise ValueError("Selected acquisition source changed: " + source)
            acquisition[name] = {"entrypoint": source, "method": method,
                                 "evidence": evidence}
        entry["acquisition"] = acquisition
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("mapped nine original or saved-derived source observations for seven exact cases")


if __name__ == "__main__":
    main()
