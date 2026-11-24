"""Bind exact saved-only CPU proofs to future recorded-only handoffs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def handoff(entry, *, root=ROOT):
    kind = entry["case_id"].rsplit("__", 1)[-1]
    if kind not in {"green_selected_drive", "adjacent_dark_drive", "second_green_drive",
                    "green_selected_stand"}:
        raise ValueError("unexpected exact saved case")
    logs = {}
    for candidate in ("primary", "fallback1"):
        name = f"cpu-camera-sync-saved-{kind}-{candidate}.log"
        log = root / name
        if not log.is_file():
            raise ValueError("saved-only fixture log missing")
        content = log.read_text()
        if (f"{entry['case_id']} {candidate} pinned saved-only positive and missing-signal negative passed" not in content
                or "originals preserved; synthetic source only" not in content):
            raise ValueError("saved-only fixture result differs")
        logs[candidate] = {"test_log": name, "test_log_sha256": sha(log),
                           "test_exit_code": 0,
                           "test_command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ROOT.name}/prove_saved.py --case {entry['case_id']} --candidate {candidate}"}
    output = f"$PWD/.runtime-work/c147332-12a-native-saved/{kind}"
    attempt = f"$PWD/.runtime-work/c147332-12a-native-attempt/{kind}"
    command = (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json"
               f" --case {entry['case_id']} --attempt {attempt} --output {output}"
               " --library $PWD/runtime/library"
               " --validator $PWD/.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck")
    return {"recorded_only": True, "command": command,
            "feedback_command": f"cat {output}/v0001/feedback.json",
            **logs["primary"], "fallback1_fixture": logs["fallback1"],
            "scope": "CPU fixture proof only; future original Native attempt must be independently reviewed"}


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("assignment_id") != ROOT.name or len(manifest.get("cases", [])) != 4:
        raise ValueError("exact four-case manifest required")
    for entry in manifest["cases"]:
        entry["post_capture"] = handoff(entry)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound four exact recorded-only post-capture handoffs with primary and fallback fixture proofs")


if __name__ == "__main__":
    main()
