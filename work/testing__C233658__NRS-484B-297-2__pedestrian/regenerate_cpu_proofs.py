"""Refresh current-construction offline, compatibility and saved-only proofs."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME = Path("runtime.py")
MANIFEST = Path("work") / HERE.name / "execution-manifest.draft.json"
VALIDATOR = Path(".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck")
TAG = os.environ.get("PEDESTRIAN_PROOF_TAG", "current3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work" / "pedestrian-output"))
    cmd = [str(ROOT / ".venv-cpu/bin/python"), str(RUNTIME), *map(str, args)]
    result = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    log.write_text((result.stdout + result.stderr).rstrip() + "\n", encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {' '.join(cmd)}; see {log}")
    return " ".join([".venv-cpu/bin/python", "runtime.py", *map(str, args)])


def main():
    manifest = json.loads((ROOT / MANIFEST).read_text())
    offline = []
    compat = []
    saved = []
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        short = cid.split("__")[-1]
        folder = HERE / "cases" / short
        for candidate in ("primary", "fallback1"):
            suffix = "" if candidate == "primary" else "--candidate fallback1"
            out = Path(".runtime-work") / f"pedestrian-offline-{short}-{candidate}-{TAG}"
            args = ["offline", "--manifest", MANIFEST, "--case", cid,
                    "--output", out]
            if candidate != "primary":
                args += ["--candidate", candidate]
            log = folder / f"proof-offline-{candidate}.log"
            command = run(args, log)
            offline.append({"case_id": cid, "candidate_id": candidate, "command": command,
                            "exit_code": 0, "log": str(log.relative_to(HERE)), "log_sha256": sha(log)})
            out = Path(".runtime-work") / f"pedestrian-compat-{short}-{candidate}-{TAG}"
            args = ["compatibility", "--manifest", MANIFEST, "--case", cid,
                    "--output", out, "--library", "runtime/library", "--validator", VALIDATOR]
            if candidate != "primary":
                args += ["--candidate", candidate]
            output_log = folder / f"proof-compatibility-{candidate}-command.log"
            command = run(args, output_log)
            source = ROOT / out
            receipt = folder / f"proof-compatibility-{candidate}.json"
            receipt.write_bytes((source / "compatibility.json").read_bytes())
            analysis_log = folder / f"proof-compatibility-{candidate}-analysis.log"
            analysis_log.write_bytes((source / "compatibility-analysis.log").read_bytes())
            neg = folder / f"proof-compatibility-{candidate}-negative.log"
            neg.write_bytes((source / "negative-analysis.log").read_bytes())
            compat.append({"case_id": cid, "candidate_id": candidate, "command": command,
                           "exit_code": 0, "receipt": str(receipt.relative_to(HERE)),
                           "sha256": sha(receipt), "log": str(analysis_log.relative_to(HERE)),
                           "log_sha256": sha(analysis_log),
                           "negative_log": str(neg.relative_to(HERE)),
                           "negative_log_sha256": sha(neg)})
            if candidate == "primary":
                saved_out = Path(".runtime-work") / f"pedestrian-saved-{short}-{TAG}"
                args = ["process-saved", "--manifest", MANIFEST, "--case", cid,
                        "--attempt", out, "--output", saved_out, "--library", "runtime/library",
                        "--validator", VALIDATOR]
                saved_log = folder / "proof-saved-only.log"
                command = run(args, saved_log)
                saved.append({"case_id": cid, "command": command, "exit_code": 0,
                              "log": str(saved_log.relative_to(HERE)), "log_sha256": sha(saved_log)})
        print(short, "offline, compatibility, saved-only passed", flush=True)
    write_json(HERE / "cpu-offline-proofs.json", offline)
    write_json(HERE / "cpu-compatibility-proofs.json", compat)
    write_json(HERE / "cpu-saved-proofs.json", saved)


if __name__ == "__main__":
    main()
