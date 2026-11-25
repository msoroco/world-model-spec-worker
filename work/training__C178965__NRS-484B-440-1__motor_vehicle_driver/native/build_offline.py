"""Bind exact C178965 Native proposal to runtime offline."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "training__C178965__NRS-484B-440-1__motor_vehicle_driver"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = []
    for number in (1, 2, 3):
        tag = f"probe_0{number}"
        case = ASSIGNMENT + "__" + tag
        prefix = "work/" + ASSIGNMENT + "/"
        config = json.loads((ROOT / "cases" / f"{tag}.json").read_text())
        files = [{"path": "config.json", "source": prefix + f"native/cases/{tag}.json",
                  "content": (ROOT / "cases" / f"{tag}.json").read_text()}]
        files.extend({"path": rel, "source": prefix + "native/" + rel,
                      "content": (ROOT / rel).read_text()}
                     for rel in ("runner.py", "finalize.py", "tests/test_runner.py", "tests/test_saved.py"))
        files.append({"path": "finalize_saved.py", "source": prefix + "finalize_saved.py",
                      "content": (ROOT.parent / "finalize_saved.py").read_text()})
        construction_path = ROOT / "cases" / f"{tag}-construction.json"
        write(construction_path, {
            "format": "c178965-exact-native-proposal-v2", "case_id": case,
            "law_id": "NRS-484B-440-1", "cell_id": "C178965", "actor": "motor_vehicle_driver",
            "entrypoint": "runner.py",
            "recording_description": config["recording_description"],
            "measurement_plan": {"saved_finalizer": "finalize.py", "source_join": "600 original Native frames"},
            "static_checks": ["exact case and fixed cell", "surveyed on/off pavement targets",
                              "two 200-foot approach stations and nine rays each"],
            "termination_rules": ["600 synchronized frames", "fail on missing original source"],
            "mechanisms": ["surveyed roadside stop", "other vehicle motion",
                           "engine-command failure injection only in probe_03"],
            "files": files,
        })
        cases.append({"case_id": case, "construction": f"cases/{tag}-construction.json",
                      "construction_sha256": sha(construction_path)})
    write(ROOT / "manifest.json", {
        "format": "c178965-partial-offline-manifest-v1",
        "cases": cases,
        "physical_completion": False,
    })
    print(json.dumps({"construction_sha256": [case["construction_sha256"] for case in cases],
                      "manifest_sha256": sha(ROOT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
