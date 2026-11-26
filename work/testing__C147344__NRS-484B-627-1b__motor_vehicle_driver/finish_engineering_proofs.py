"""Bind six source-gated engineering cases to final-hash CPU proof receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from engineering_sweep_station import engineering_station
from reviewed_scene import ASSIGNMENT
from bind_pinned_diagnostic import bind

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SCRATCH = REPO / ".runtime-work/c147344-owner-nov26"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_copy(source: Path, target: Path) -> None:
    content = source.read_text(encoding="utf-8")
    target.write_text(content.rstrip() + "\n" if content else "", encoding="utf-8")


def run(script: str, arguments: list[str], log: Path, expected: int = 0) -> int:
    command = [sys.executable, str(HERE / script), *arguments]
    result = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                            capture_output=True, text=True, timeout=180)
    log.write_text((result.stdout + result.stderr).rstrip() + "\n", encoding="utf-8")
    if result.returncode != expected:
        raise ValueError(f"{script} returned {result.returncode}, expected {expected}: {log}")
    return result.returncode


def main() -> None:
    manifest = json.loads((HERE / "engineering-diagnostic-manifest.json").read_text())
    for item in manifest["cases"]:
        case = item["case_id"]
        if engineering_station(case) is None:
            raise ValueError("unlisted engineering case")
        suffix = case.removeprefix(ASSIGNMENT + "__")
        folder = HERE / "cases" / suffix
        attempt = SCRATCH / f"compat-v3-{suffix}"
        saved = SCRATCH / f"saved-v3-{suffix}.log"
        if not (attempt / "compatibility.json").exists() or not saved.exists():
            raise ValueError("pinned compatibility or saved receipt absent")
        bind(attempt / "compatibility.json", saved, suffix)
        for name, source in (
            ("compatibility.json", attempt / "compatibility.json"),
            ("cpu-compat-analysis.log", attempt / "compatibility-analysis.log"),
            ("negative-analysis.log", attempt / "negative-analysis.log"),
            ("offline.log", SCRATCH / f"offline-final-{suffix}" / "offline.log"),
        ):
            clean_copy(source, folder / name)
        if sha(folder / "compatibility.json") != sha(attempt / "compatibility.json"):
            raise ValueError("compatibility receipt normalization changed content")
        fixtures = []
        for kind, short in (("complete_motion", "complete"),
                            ("incomplete_motion", "incomplete"),
                            ("missing_evidence", "missing")):
            result = folder / f"physical-{short}.json"
            log = folder / f"physical-{short}.log"
            result.unlink(missing_ok=True)
            args = ["--case", case, "--kind", kind, "--attempt", str(attempt),
                    "--output", str(result)]
            run("prove_engineering_physical.py", args, log)
            fixtures.append({"kind": kind,
                             "command": f"{sys.executable} work/{ASSIGNMENT}/prove_engineering_physical.py " + " ".join(args),
                             "exit_code": 0, "log": str(log.relative_to(HERE)),
                             "log_sha256": sha(log), "result": str(result.relative_to(HERE)),
                             "result_sha256": sha(result)})
        life_log = folder / "physical-lifecycle.log"
        life_args = ["--case", case, "--attempt", str(attempt), "--saved-receipt", str(saved)]
        run("prove_engineering_lifecycle.py", life_args, life_log)
        write(folder / "physical-preparation.json", {
            "format": "c147344-diagnostic-physical-preparation", "case_id": case,
            "construction_sha256": item["construction_sha256"],
            "source_kind": "synthetic_software_fixture", "fixtures": fixtures,
            "lifecycle": {"command": f"{sys.executable} work/{ASSIGNMENT}/prove_engineering_lifecycle.py " + " ".join(life_args),
                          "scope": "synthetic lifecycle protocol only", "exit_code": 0,
                          "events": ["capture_finished", "encoders_closed", "restoration_verified",
                                     "native_exit", "owner_released", "saved_processing_started"],
                          "log": str(life_log.relative_to(HERE)), "log_sha256": sha(life_log)},
        })
        for mode, name, expected in (("diagnostic-positive", "delivery-positive", 0),
                                     ("delivery-negative", "delivery-negative", 1)):
            run("prove_engineering_delivery.py", ["--case", case, "--mode", mode],
                folder / f"{name}.log", expected)
        print(suffix, sha(folder / "physical-preparation.json"))


if __name__ == "__main__":
    main()
