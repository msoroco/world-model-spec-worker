"""Release a closed Native attempt only after its original process exits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_process_alive(identity: dict) -> bool:
    pid, expected = identity.get("pid"), identity.get("proc_start_ticks")
    if type(pid) is not int or pid <= 0 or type(expected) is not int or expected <= 0:
        raise ValueError("Native process identity invalid")
    stat_path = Path(f"/proc/{pid}/stat")
    if not stat_path.exists():
        return False
    stat = stat_path.read_text(encoding="utf-8")
    return int(stat.rsplit(")", 1)[1].split()[19]) == expected


def release(attempt: Path, *, liveness_probe=same_process_alive) -> dict:
    attempt = Path(attempt).resolve()
    if not any(parent.name == ".runtime-work" for parent in attempt.parents):
        raise ValueError("owner release requires private Native attempt")
    release_path = attempt / "owner-release.json"
    if release_path.exists():
        raise ValueError("retain previous owner release")
    status_path, exit_path = (attempt / "native-run-status.json",
                              attempt / "native-exit.json")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    exited = json.loads(exit_path.read_text(encoding="utf-8"))
    identity = status.get("native_process")
    if (status.get("errors") != [] or
            not isinstance(status.get("capture"), dict) or
            status["capture"].get("frames") != 900 or
            not isinstance(status.get("restoration"), dict) or
            status["restoration"].get("restored") is not True or
            not isinstance(identity, dict) or
            exited.get("event") != "native_exit_pending_process_termination" or
            exited.get("case_id") != status.get("case_id") or
            exited.get("native_process") != identity or
            exited.get("native_run_status_sha256") != sha(status_path)):
        raise ValueError("closed Native exit identity or restoration differs")
    if liveness_probe(identity):
        raise ValueError("Native process is still running")
    result = {"event": "owner_released", "case_id": status["case_id"],
              "native_exit_sha256": sha(exit_path),
              "native_run_status_sha256": sha(status_path),
              "native_process": identity,
              "physical_acceptance_claimed": False}
    release_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def verify_release(attempt: Path, *, liveness_probe=same_process_alive) -> dict:
    attempt = Path(attempt).resolve()
    if not any(parent.name == ".runtime-work" for parent in attempt.parents):
        raise ValueError("saved work requires private Native attempt")
    status_path, exit_path, release_path = (attempt / "native-run-status.json",
                                           attempt / "native-exit.json",
                                           attempt / "owner-release.json")
    for path in (status_path, exit_path, release_path):
        if not path.is_file():
            raise ValueError("Native exit and owner release required")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    exited = json.loads(exit_path.read_text(encoding="utf-8"))
    released = json.loads(release_path.read_text(encoding="utf-8"))
    identity = status.get("native_process")
    if (status.get("errors") != [] or
            not isinstance(status.get("capture"), dict) or
            status["capture"].get("frames") != 900 or
            not isinstance(status.get("restoration"), dict) or
            status["restoration"].get("restored") is not True or
            not isinstance(identity, dict) or
            exited.get("event") != "native_exit_pending_process_termination" or
            exited.get("case_id") != status.get("case_id") or
            exited.get("native_process") != identity or
            exited.get("native_run_status_sha256") != sha(status_path) or
            released.get("event") != "owner_released" or
            released.get("case_id") != status.get("case_id") or
            released.get("native_process") != identity or
            released.get("native_exit_sha256") != sha(exit_path) or
            released.get("native_run_status_sha256") != sha(status_path)):
        raise ValueError("Native exit or owner release identity differs")
    if liveness_probe(identity):
        raise ValueError("Native owner is still live")
    return released


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(release(args.attempt), indent=2))
