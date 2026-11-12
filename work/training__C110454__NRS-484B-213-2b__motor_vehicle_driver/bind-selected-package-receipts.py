"""Bind current exact candidate diagnostics and saved-only handoff fields."""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from source_join_audit import read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PROOFS = HERE / "update024-selected-proofs"
INDEX = HERE / "update025-source-receipts-index.json"
PY = ".venv-cpu/bin/python"


def command(*args):
    return shlex.join(args)


def acquisition(construction):
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    channels = {item["name"] for item in construction["recording_description"]["channels"]}
    outputs = {}
    for name in set(config.get("required_atoms", [])) | channels:
        if name == "camera_frame_join":
            sources = "video_frames.jsonl and four named original camera streams"
        elif name.startswith("st."):
            sources = "road_geometry.json and original statutory_context.json or context.json"
        else:
            sources = "native_samples.jsonl and capture/evidence.jsonl joined by video_frames.jsonl"
        outputs[name] = {"entrypoint": "runner.py",
                         "method": "retained Native frame/map source, rebuilt by saved finalize.py",
                         "evidence": sources}
    return outputs


def build() -> dict:
    manifest = read(MANIFEST)
    index = read(INDEX)
    require(index.get("manifest_sha256") == sha(MANIFEST) and
            index.get("candidate_count") == 24 and
            index.get("physical_acceptance_claimed") is False,
            "Retained compatibility index differs from current selection")
    retained = {(row["case_id"], row["candidate_id"]): row for row in index["candidates"]}
    require(len(retained) == 24, "Duplicate retained candidate receipt")
    for entry in manifest["cases"]:
        case, suffix = entry["case_id"], entry["case_id"].removeprefix(HERE.name + "__")
        construction = read(HERE / entry["construction"])
        for candidate in (entry, *entry["candidates"]):
            ident = candidate["id"]
            row = retained.get((case, ident))
            require(row is not None and row["construction_sha256"] ==
                    candidate["construction_sha256"] and row["diagnostic_only"] is True,
                    "Retained candidate identity differs")
            proof_dir = PROOFS / suffix / ident
            proof = read(proof_dir / "proof.json")
            offline = proof_dir / "offline.log"
            saved = proof_dir / "process-saved.log"
            require(proof["manifest_sha256"] == sha(MANIFEST) and
                    proof["construction_sha256"] == candidate["construction_sha256"] and
                    proof["offline_log_sha256"] == sha(offline) and
                    proof["process_saved_log_sha256"] == sha(saved),
                    "Selected offline or saved proof changed")
            files = row["files"]
            receipt = HERE / files["compatibility.json"]["path"]
            analysis = HERE / files["compatibility-analysis.log"]["path"]
            negative = HERE / files["negative-analysis.log"]["path"]
            require(all(sha(HERE / item["path"]) == item["sha256"]
                        for item in files.values()),
                    "Retained compatibility file changed")
            candidate["offline"] = {
                "command": command(PY, "runtime.py", "offline", "--manifest",
                                   f"work/{HERE.name}/execution-manifest.json", "--case", case,
                                   "--candidate", ident, "--output", "${OFFLINE_DIR}",
                                   "--python", PY),
                "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
                "log": str(offline.relative_to(HERE)), "log_sha256": sha(offline)}
            candidate["compatibility"] = {
                "receipt": str(receipt.relative_to(HERE)), "sha256": sha(receipt),
                "log": str(analysis.relative_to(HERE)),
                "negative_log": str(negative.relative_to(HERE))}
            if ident == "primary":
                entry["negative"] = {"log": str(negative.relative_to(HERE)),
                                     "log_sha256": sha(negative)}
                entry["post_capture"] = {
                    "recorded_only": True,
                    "command": command(PY, "runtime.py", "process-saved", "--manifest",
                                       f"work/{HERE.name}/execution-manifest.json", "--case", case,
                                       "--attempt", "${ATTEMPT_DIR}", "--output", "${PROCESSED_DIR}",
                                       "--library", "${DECODER_LIBRARY}", "--validator", "${VALIDATOR}",
                                       "--owner-release-receipt", "${OWNER_RELEASE_RECEIPT}"),
                    "feedback_command": command(PY, "-m", "json.tool",
                                                "${PROCESSED_DIR}/v0001/feedback.json"),
                    "test_log": str(saved.relative_to(HERE)),
                    "test_log_sha256": sha(saved), "test_exit_code": 0}
                entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT"}
                entry["acquisition"] = acquisition(construction)
    sys.path.insert(0, str(ROOT / "runtime/pipeline"))
    sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
    from scenario_pipeline.worker_exchange.candidate_constructions import validate as validate_candidates
    from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
    plan = read(HERE / "case-plan.json")
    for entry in manifest["cases"]:
        validate_candidates(HERE, entry, plan["law_id"], plan["cell_id"],
                            required=True, require_alternate=True, candidate_count=4)
    check_receipts(ROOT, HERE, manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": len(manifest["cases"]), "candidates": len(retained),
            "manifest_sha256": sha(MANIFEST), "physical_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(build()))
