"""Bind each exact case to its diagnostic recipe without changing offline proofs."""
from __future__ import annotations

import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    path=HERE/"execution-manifest.json";manifest=json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix=entry["case_id"].removeprefix(HERE.name+"__")
        recipe=HERE/"cases"/suffix/"fixture-recipe.json"
        if not recipe.is_file():raise ValueError("diagnostic recipe missing: "+suffix)
        entry["fixture_recipe"]=f"work/{HERE.name}/cases/{suffix}/fixture-recipe.json"
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print("three exact diagnostic recipes bound")


if __name__=="__main__":main()
