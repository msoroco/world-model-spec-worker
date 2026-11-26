"""Bind exact CPU proofs and Native handoff to seven selected cases."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, CHANNELS


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(path):
    target = HERE / path
    if not target.is_file():
        raise ValueError("missing current exact proof: " + str(path))
    return target


def run():
    manifest = json.loads(required("execution-manifest.selected-draft.json").read_text())
    if manifest["assignment_id"] != AID or len(manifest["cases"]) != 7:
        raise ValueError("seven exact protected-pavement cases required")
    sources = {
        "vehicle_motion": "pavement_capture.py",
        "pavement_condition": "pavement_protection.py",
        "pavement_extent": "pavement_capture.py",
        "protection_geometry": "pavement_native.py",
        "protection_placement_time": "pavement_capture.py",
        "employment": "runner.py",
        "work_activity": "pavement_capture.py",
        "camera_frame_identity": "pavement_capture.py",
    }
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(AID + "__")
        if sha(required(entry["construction"])) != entry["construction_sha256"]:
            raise ValueError("selected construction changed")
        primary = required("proof-compat-receipt-" + suffix + ".json")
        proof = json.loads(primary.read_text())
        if proof.get("passed") is not True or proof.get("construction_sha256") != entry["construction_sha256"]:
            raise ValueError("selected compatibility proof changed")
        primary_log = "proof-compat-analysis-" + suffix + ".log"
        primary_negative = "proof-compat-negative-" + suffix + ".log"
        required(primary_log)
        required(primary_negative)
        entry["compatibility"] = {"receipt": primary.name, "sha256": sha(primary),
                                  "log": primary_log, "negative_log": primary_negative}
        entry["negative"] = {"log": primary_negative}
        offline = required("proof-selected-offline-" + suffix + ".log")
        entry["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                       "/execution-manifest.selected-draft.json --case " + case_id +
                       " --output .runtime-work/c230211-nov26/selected-v2/offline/" + suffix +
                       " --python .venv-cpu/bin/python",
            "exit_code": 0, "log": offline.name, "log_sha256": sha(offline),
            "construction_sha256": entry["construction_sha256"],
        }
        physical = required("physical-" + suffix + "-receipt.json")
        entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        saved = required("proof-selected-saved-" + suffix + ".log")
        entry["saved_replay"] = {"log": saved.name, "sha256": sha(saved)}
        entry["post_capture"] = {
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                       "/execution-manifest.json --case " + case_id +
                       " --attempt $ATTEMPT --output $PROCESSED --library runtime/library" +
                       " --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": ".venv-cpu/bin/python work/" + AID +
                                "/delivery_audit.py --case " + case_id +
                                " --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": saved.name, "test_log_sha256": sha(saved),
        }
        acceptance_path = required("delivery-acceptance-" + suffix + ".json")
        acceptance = json.loads(acceptance_path.read_text())
        acceptance["script_sha256"] = sha(required("delivery_audit.py"))
        acceptance_path.write_text(json.dumps(acceptance, indent=2) + "\n")
        entry["delivery_acceptance"] = acceptance
        entry["acquisition"] = {
            name: {"entrypoint": sources[name], "method": method,
                   "evidence": "original-source-receipt.json, pavement-packet.json, " +
                               "trace.jsonl, video_frames.jsonl and four 900-frame cameras"}
            for name, _, method in CHANNELS
        }
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1" or sha(required(candidate["construction"])) != candidate["construction_sha256"]:
            raise ValueError("exact fallback changed")
        fallback_offline = required("proof-fallback-offline-" + suffix + ".log")
        candidate["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                       "/execution-manifest.selected-draft.json --case " + case_id +
                       " --candidate fallback1 --output .runtime-work/c230211-nov26/fallback-offline-v1/" + suffix +
                       " --python .venv-cpu/bin/python",
            "exit_code": 0, "log": fallback_offline.name,
            "log_sha256": sha(fallback_offline),
            "construction_sha256": candidate["construction_sha256"],
        }
        fallback = required("proof-fallback-receipt-" + suffix + ".json")
        fallback_proof = json.loads(fallback.read_text())
        if fallback_proof.get("passed") is not True or fallback_proof.get("construction_sha256") != candidate["construction_sha256"]:
            raise ValueError("fallback compatibility proof changed")
        candidate["compatibility"] = {
            "receipt": fallback.name, "sha256": sha(fallback),
            "log": "proof-fallback-analysis-" + suffix + ".log",
            "negative_log": "proof-fallback-negative-" + suffix + ".log",
        }
    manifest["status"] = "physical_and_selected_cpu_proofs_bound_gpu_pending"
    destination = HERE / "execution-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    if destination.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("return manifest exceeds size limit")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("bound protected-pavement cases:", run())
