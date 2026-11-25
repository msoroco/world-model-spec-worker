"""Bind current exact constructions, measurement contracts and fixture recipes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    selected = json.loads((HERE / "selected-construction-manifest.json").read_text())
    entries = []
    for item in selected["cases"]:
        suffix = item["case_id"].rsplit("__", 1)[-1]
        entry = dict(item)
        entry.update({"kind": "delivery",
            "measurement_contract": "selected-contracts/" + suffix + ".json",
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "c104496-saved-analysis-v1"},
            "fixture_recipe": "work/" + HERE.name + "/source-fixture/" +
                              suffix + "/recipe.json",
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"}})
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest",
        "assignment_id": HERE.name, "status": "selected_cpu_compatibility_in_progress",
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries}
    path = HERE / "selected-compatibility-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"selected_cases": len(entries),
                      "runtime_manifest_sha256": manifest["runtime_manifest_sha256"]}))


if __name__ == "__main__":
    main()
