"""Rebind selected signal diagnostics to live adapter JSON graphs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    converted = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        if entry["fixture_recipe"] in converted:
            entry["fixture_recipe"] = converted[entry["fixture_recipe"]]
            print(json.dumps({"case": suffix, "shared_recipe": True}))
            continue
        original_recipe_path = entry["fixture_recipe"]
        old_recipe = json.loads((ROOT / entry["fixture_recipe"]).read_text())
        old_spec = json.loads((ROOT / old_recipe["generator"]["source"]).read_text())
        if len(old_spec["graphs"]) != 800:
            raise ValueError("Expected 800 frame graphs")
        for graph in old_spec["graphs"]:
            if not graph["path"].endswith(".pkl"):
                raise ValueError("Unexpected graph format")
            graph["path"] = graph["path"][:-4] + ".adapter.json"
        frame_path = "capture/native/frames.jsonl"
        rows = [json.loads(line) for line in old_spec["files"][frame_path].splitlines()]
        if len(rows) != 800:
            raise ValueError("Expected 800 frame map rows")
        for row in rows:
            row["base"] = row["base"].replace(".pkl", ".adapter.json")
            if "abstract" in row:
                row["abstract"] = row["abstract"].replace(".pkl", ".adapter.json")
            row["adapter_graph"] = row["base"]
        old_spec["files"][frame_path] = "\n".join(json.dumps(row) for row in rows) + "\n"
        new_spec = HERE / f"update500-{suffix}-diagnostic.json"
        new_recipe_path = HERE / f"update500-{suffix}-diagnostic-recipe.json"
        save(new_spec, old_spec)
        relative = str(new_spec.relative_to(ROOT))
        old_source = old_recipe["generator"]["source"]
        old_recipe["generator"] = {"source": relative, "sha256": sha(new_spec)}
        for source in old_recipe["sources"]:
            if source["source"] == old_source:
                source["source"] = relative
                source["sha256"] = sha(new_spec)
        save(new_recipe_path, old_recipe)
        entry["fixture_recipe"] = str(new_recipe_path.relative_to(ROOT))
        converted[original_recipe_path] = entry["fixture_recipe"]
        print(json.dumps({"case": suffix, "graphs": 800, "spec_sha256": sha(new_spec)}))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
