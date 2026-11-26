"""Bind current exact constructions and offline receipts for public CPU pilot."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(suffix, candidate):
    source = REPO / ".runtime-work" / f"c24758-{suffix}-{candidate}-final2-offline-20261125/offline.log"
    target = ROOT / "native" / f"{suffix}-{candidate}-selected-prep-offline.log"
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text("\n".join(lines) + "\n")
    return str(target.relative_to(ROOT)), sha(target)


def main():
    cases = []
    for suffix in ("reference", "at_15", "contrast"):
        case = AID + "__" + suffix
        manifest = json.loads((ROOT / "native" /
            ("draft-primary-manifest.json" if suffix == "reference" else
             f"draft-{suffix}-manifest.json")).read_text())
        old = manifest["cases"][0]
        primary_log, primary_sha = log(suffix, "primary")
        fallback_log, fallback_sha = log(suffix, "fallback1")
        fallback = old["candidates"][0]
        fallback["offline"] = {"exit_code": 0,
            "construction_sha256": fallback["construction_sha256"],
            "command": "runtime.py offline --case " + case + " --candidate fallback1",
            "log": fallback_log, "log_sha256": fallback_sha}
        fallback["construction"] = "native/" + fallback["construction"]
        cases.append({"case_id": case, "kind": "delivery",
            "construction": "native/" + old["construction"],
            "construction_sha256": old["construction_sha256"],
            "candidate_risk": old["candidate_risk"], "candidates": [fallback],
            "offline": {"exit_code": 0, "construction_sha256": old["construction_sha256"],
                        "command": "runtime.py offline --case " + case + " --candidate primary",
                        "log": primary_log, "log_sha256": primary_sha},
            "measurement_contract": "measurement-contract.json",
            "fixture_recipe": "work/" + AID + "/diagnostic-recipe-" + suffix + ".json",
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"}})
    value = {"format": "worker-execution-manifest", "assignment_id": AID,
             "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
             "status": "draft_current_runtime_public_pilot", "cases": cases}
    (ROOT / "draft-execution-manifest.json").write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
