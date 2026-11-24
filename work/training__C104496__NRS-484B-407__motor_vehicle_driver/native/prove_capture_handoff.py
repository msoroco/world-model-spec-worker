"""Exercise the two acquisition entrypoint guards without contacting CARLA."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = ROOT / ".runtime-work/c104496-capture-handoff-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(branch: str):
    folder = HERE / branch
    for name in ("build", "check", "saved"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location(
            "c104496_" + branch + "_capture", folder / "capture.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def check_branch(branch: str) -> dict:
    source = HERE / branch / "drafts" / ("probe_03" if branch == "curve" else "probe_01") / "primary"
    target = SCRATCH / branch / "materialized"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    module = load(branch)
    attempts = []
    try:
        module.capture(target, target / "missing", "127.0.0.1", 2000)
    except ValueError as error:
        if "materialized bundle directory" not in str(error):
            raise
        attempts.append("unmaterialized_output_rejected")
    else:
        raise AssertionError("unmaterialized output accepted")
    sentinel = target / "native-raw-actors.jsonl"
    sentinel.write_text("existing acquisition\n")
    try:
        module.capture(target, target, "127.0.0.1", 2000)
    except ValueError as error:
        if "Retain prior acquisition" not in str(error):
            raise
        attempts.append("existing_acquisition_rejected")
    else:
        raise AssertionError("existing acquisition accepted")
    sentinel.unlink()
    old = sys.modules.get("carla")
    probe = types.ModuleType("carla")

    class StopBeforeClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("CARLA client creation intercepted by CPU test")

    probe.Client = StopBeforeClient
    sys.modules["carla"] = probe
    try:
        module.capture(target, target, "127.0.0.1", 2000)
    except RuntimeError as error:
        if "intercepted by CPU test" not in str(error):
            raise
        attempts.append("materialized_bundle_reaches_client_boundary")
    finally:
        if old is None:
            sys.modules.pop("carla", None)
        else:
            sys.modules["carla"] = old
    return {"branch": branch, "checks": attempts,
            "capture_sha256": sha(HERE / branch / "capture.py"),
            "carla_server_contacted": False}


def main():
    rows = [check_branch(branch) for branch in ("crest", "curve")]
    proof = {"format": "c104496-native-capture-handoff-proof-v1",
             "assignment_id": HERE.parent.name, "branches": rows,
             "passed": all(len(row["checks"]) == 3 for row in rows),
             "physical_motion_or_visibility_proven": False}
    path = HERE / "capture-handoff-proof.json"
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": proof["passed"], "checks": 6,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
