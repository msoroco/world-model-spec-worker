"""Bind authored C104496 semantic stages to the current selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = {"relevance_batch": "proposals/relevance-batch.json",
         "relevance": "proposals/relevance.json",
         "template": "proposals/template.json",
         "bindings": "proposals/bindings.json",
         "cases": "proposals/cases.json"}


def ref(name):
    path = HERE / name
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    stages = {stage: ref(name) for stage, name in FILES.items()}
    template = json.loads((HERE / FILES["template"]).read_text())
    count = len(template["structure"]["judgment_calls_needed"])
    stages["judgment_observables"] = [
        ref("proposals/judgment-observables-" + str(i) + ".json")
        for i in range(1, count + 1)]
    index = {"format": "worker-semantic-delivery",
             "assignment_id": HERE.name, "stages": stages,
             "original_physical_acceptance_claimed": False}
    path = HERE / "proposals/semantic-index.json"
    path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"stage_files": count + len(FILES),
                      "index_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
