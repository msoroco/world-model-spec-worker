"""CPU check for the source-gated root Native capture entrypoint."""
import json
from pathlib import Path
from capture import check

config = json.loads(Path(__file__).resolve().parents[1].joinpath("config.json").read_text())
assert check(config)["frames"] == 600
assert len(config["supported_case_ids"]) == 13
print("root exact Native capture plan: passed")
