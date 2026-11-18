"""Retain candidate-specific Native context while migrating diagnostic graphs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate in entry["candidates"]:
            ident = candidate["id"]
            old_recipe_path = HERE / f"update015-{suffix}-{ident}-recipe.json"
            recipe = json.loads(old_recipe_path.read_text())
            spec = json.loads((ROOT / recipe["generator"]["source"]).read_text())
            if len(spec["graphs"]) != 480:
                raise ValueError("Expected 480 candidate frame graphs")
            for graph in spec["graphs"]:
                if not graph["path"].endswith(".pkl"):
                    raise ValueError("Unexpected candidate graph format")
                graph["path"] = graph["path"][:-4] + ".adapter.json"
            key = "capture/native/frames.jsonl"
            rows = [json.loads(line) for line in spec["files"][key].splitlines()]
            if len(rows) != 480:
                raise ValueError("Expected 480 candidate frame rows")
            for row in rows:
                row["base"] = row["base"].replace(".pkl", ".adapter.json")
                row["abstract"] = row["abstract"].replace(".pkl", ".adapter.json")
                row["adapter_graph"] = row["base"]
            spec["files"][key] = "\n".join(json.dumps(row) for row in rows) + "\n"
            spec_path = HERE / f"update043-{suffix}-{ident}-diagnostic.json"
            recipe_path = HERE / f"update043-{suffix}-{ident}-recipe.json"
            save(spec_path, spec)
            source = str(spec_path.relative_to(ROOT))
            old_source = recipe["generator"]["source"]
            recipe["generator"] = {"source": source, "sha256": sha(spec_path)}
            for item in recipe["sources"]:
                if item["source"] == old_source:
                    item["source"] = source
                    item["sha256"] = sha(spec_path)
            save(recipe_path, recipe)
            print(json.dumps({"case": suffix, "candidate": ident,
                              "recipe_sha256": sha(recipe_path)}))


if __name__ == "__main__":
    main()
