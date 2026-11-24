"""Give finite sweep cases the batch-qualified IDs required by preparation."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT / ".runtime-work/c144550-physical-sweeps"
NAMES = [
    "signal-appropriateness-pending-0000",
    "signal-appropriateness-pending-0001",
    "signal-appropriateness-pending-0002",
    "safety-ascertainment-pending-0000",
    "safety-ascertainment-pending-0001",
]
MAPPING = {name: HERE.name + "__" + name for name in NAMES}


def change(value):
    if isinstance(value, str):
        return MAPPING.get(value, value)
    if isinstance(value, list):
        return [change(item) for item in value]
    if isinstance(value, dict):
        return {key: change(item) for key, item in value.items()}
    return value


def apply(path):
    value = json.loads(path.read_text())
    updated = change(value)
    path.write_text(json.dumps(updated, indent=2) + "\n")


def main():
    for path in (
        STAGE / "cases.json",
        HERE / "physical-sweep-stage-proof.json",
        HERE / "proposals/cases.json",
        HERE / "case-plan.json",
        HERE / "config.json",
        HERE / "execution-manifest.json",
    ):
        apply(path)
    config_path = HERE / "config.json"
    config = json.loads(config_path.read_text())
    zero = HERE.name + "__left_signal_at_departure_clear_gap"
    for case_id in [zero, *MAPPING.values()]:
        if case_id not in config["supported_case_ids"]:
            config["supported_case_ids"].append(case_id)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(json.dumps({"qualified_case_ids": list(MAPPING.values())}))


if __name__ == "__main__":
    main()
