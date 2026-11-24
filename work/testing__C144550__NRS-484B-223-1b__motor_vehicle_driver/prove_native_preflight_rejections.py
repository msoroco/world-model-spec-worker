"""Reproduce Native-preflight rejection paths with isolated CPU fixtures."""

import hashlib
import json
import pathlib
import shutil
import shlex
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "native_delivery_preflight.py"
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def run(attempt, case_id, owner, log_name, expected):
    command = [str(ROOT / ".venv-cpu/bin/python"), str(SCRIPT), "--attempt", str(attempt),
               "--case", case_id, "--owner-receipt", str(owner)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = HERE / log_name
    log.write_text(result.stdout + result.stderr)
    if result.returncode == 0 or expected not in result.stderr:
        raise ValueError("Native preflight did not reject expected CPU fixture: " + log_name)
    return {"command": shlex.join(command), "log": log_name, "sha256": sha(log),
            "expected_error": expected, "negative_exit_code": result.returncode}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["cases"][0]
    case_id = entry["case_id"]
    tokens = shlex.split(entry["post_capture"]["command"])
    source = (ROOT / tokens[tokens.index("--attempt") + 1]).resolve()
    work = ROOT / ".runtime-work/c144550-native-preflight-negative-proof"
    work.mkdir(parents=True, exist_ok=True)
    missing_owner = work / "missing-owner.json"
    rows = []
    rows.append(run(source, case_id, missing_owner, "native-preflight-diagnostic-rejection.log",
                    "Native non-diagnostic provenance required"))
    unsealed = work / "unsealed"
    unsealed.mkdir(exist_ok=True)
    (unsealed / "acquisition-provenance.json").write_text(json.dumps(
        {"provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
    rows.append(run(unsealed, case_id, missing_owner, "native-preflight-unsealed-rejection.log",
                    "Native capture seal required"))
    forged = work / "forged-owner"
    forged.mkdir(exist_ok=True)
    names = ["construction.json", "runner.py", "config.json", "lane_context.json",
             "lane_history.jsonl", "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             *(name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference"))]
    for name in names:
        destination = forged / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
    (forged / "acquisition-provenance.json").write_text(json.dumps(
        {"provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
    selection = json.loads((source / "candidate-selection.json").read_text())
    selection["manifest_sha256"] = sha(MANIFEST)
    (forged / "candidate-selection.json").write_text(json.dumps(selection) + "\n")
    sources = {name: sha(forged / name) for name in names}
    revision = {"construction_sha256": sha(forged / "construction.json"),
                "runner_sha256": sha(forged / "runner.py")}
    seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": False, "frames": 900,
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "source_digest": digest(sources), "sources": sources, "native_revision": revision}
    (forged / "capture-seal.json").write_text(json.dumps(seal) + "\n")
    native_exit = {"event": "native_exit", "capture_seal_sha256": sha(forged / "capture-seal.json"),
                   "native_revision": revision}
    (forged / "native-exit.json").write_text(json.dumps(native_exit) + "\n")
    false_owner = work / "false-owner.json"
    false_owner.write_text(json.dumps({"event": "owner_released", "operator_attested": False,
                                      "native_construction_sha256": revision["construction_sha256"],
                                      "native_exit_sha256": sha(forged / "native-exit.json"),
                                      "no_resource_operation_performed": True}) + "\n")
    rows.append(run(forged, case_id, false_owner, "native-preflight-owner-rejection.log",
                    "Owner release does not bind Native exit"))
    index = {"format": "worker-native-preflight-negative-cpu-proof", "case_id": case_id,
             "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
             "proof_driver": pathlib.Path(__file__).name, "proof_driver_sha256": sha(__file__),
             "scope": "Three rejection branches only; forged fixtures are never Native evidence",
             "negative_proofs": rows, "positive_native_proof": False}
    (HERE / "native-preflight-proof.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"rejections": len(rows), "index_sha256": sha(HERE / "native-preflight-proof.json")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
