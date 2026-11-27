"""Check each exact inline Native construction without contacting CARLA."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from capture_plan import AID, CASES

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_case(suffix: str, candidate: str) -> dict:
    folder = ROOT / "cases" / suffix
    if candidate == "fallback1":
        folder = folder / "fallback1"
    proposal = json.loads((folder / "construction.json").read_text())
    assert proposal["case_id"] == AID + "__" + suffix
    assert proposal["entrypoint"] == "runner.py"
    assert len(proposal["files"]) >= 6
    with tempfile.TemporaryDirectory(prefix="c135709-bundle-", dir=SCRATCH) as name:
        output = Path(name)
        for entry in proposal["files"]:
            target = output / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["content"], encoding="utf-8")
            if entry["path"] in ("runner.py", "capture_plan.py", "geometry.py",
                                 "parking_controller.py", "original_source_contract.py",
                                 "finalize.py"):
                assert digest(target) == digest(ROOT / "native" / entry["path"])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-B", "runner.py", "--check"]
        checked = subprocess.run(command, cwd=output, env=env, capture_output=True,
                                 text=True, timeout=30)
        assert checked.returncode == 0, checked.stderr
        result = json.loads(checked.stdout)
        assert result["case_id"] == proposal["case_id"]
        assert result["original_native_observed"] is False
        tests = subprocess.run([sys.executable, "-B", "-m", "unittest",
                                "discover", "-s", "tests"], cwd=output, env=env,
                               capture_output=True, text=True, timeout=30)
        assert tests.returncode == 0, tests.stderr
        config = json.loads((output / "config.json").read_text())
        config["case_id"] = AID + "__not_an_exact_case"
        (output / "config.json").write_text(json.dumps(config) + "\n")
        negative = subprocess.run(command, cwd=output, env=env, capture_output=True,
                                  text=True, timeout=30)
        assert negative.returncode != 0 and "exact case required" in negative.stderr
    return {"case_id": proposal["case_id"], "candidate_id": candidate,
            "construction_sha256": digest(folder / "construction.json"),
            "check_exit_code": 0, "unit_exit_code": 0,
            "wrong_case_rejected": True, "carla_contacted": False}


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    rows = [check_case(suffix, candidate) for suffix in CASES
            for candidate in ("primary", "fallback1")]
    print(json.dumps({"format": "restricted-zone-exact-construction-proof-v1",
                      "cases": rows, "selected_for_delivery": False,
                      "physical_or_legal_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
