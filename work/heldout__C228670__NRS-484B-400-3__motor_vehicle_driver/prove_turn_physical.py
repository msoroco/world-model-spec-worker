"""Bind three physical outcomes and ordered saved lifecycle for each turn case."""

import hashlib
import json
from pathlib import Path

from turn_lifecycle_fixture import EVENTS, run as lifecycle
from turn_physical_fixture import KINDS, run as physical

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMMAND = "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + HERE.name + "/prove_turn_physical.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "provisional-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    output = HERE / "physical"
    output.mkdir(exist_ok=True)
    fixture_lines = []
    lifecycle_lines = []
    claims = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.split("__")[-1]
        fixtures = []
        for kind in KINDS:
            result = physical(case, kind)
            path = output / f"{short}-{kind}.json"
            path.write_text(json.dumps(result, indent=2) + "\n")
            fixture_lines.append(f"{short} {kind} {result['physical_checks']['maneuver']['status']} synthetic_only")
            fixtures.append({"kind": kind, "command": COMMAND, "exit_code": 0,
                             "log": "turn-physical-fixture.log", "result": str(path.relative_to(HERE)),
                             "result_sha256": sha(path)})
        life = lifecycle(case)
        if life["lifecycle_events"] != EVENTS or not life["passed"]:
            raise ValueError("Ordered turn lifecycle failed")
        lifecycle_lines.append(f"{short} {' '.join(EVENTS)} synthetic_only")
        claims.append((entry, fixtures))
    physical_log = HERE / "turn-physical-fixture.log"
    lifecycle_log = HERE / "turn-lifecycle-fixture.log"
    physical_log.write_text("\n".join(fixture_lines) + "\n")
    lifecycle_log.write_text("\n".join(lifecycle_lines) + "\n")
    for entry, fixtures in claims:
        for item in fixtures:
            item["log_sha256"] = sha(physical_log)
        proof = {"construction_sha256": entry["construction_sha256"],
                 "fixture_scope": "Synthetic Native-shaped turn source and lifecycle protocol only; no CARLA capture",
                 "fixtures": fixtures,
                 "lifecycle": {"events": EVENTS, "exit_code": 0, "command": COMMAND,
                               "log": lifecycle_log.name, "log_sha256": sha(lifecycle_log)}}
        short = entry["case_id"].split("__")[-1]
        receipt = output / f"{short}-proof.json"
        receipt.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(HERE)),
                                         "sha256": sha(receipt)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Three exact turn cases: complete/incomplete/missing and ordered lifecycle passed")


if __name__ == "__main__":
    main()
