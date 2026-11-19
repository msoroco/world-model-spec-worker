"""Move exact-case diagnostic graph sources to the current JSON adapter format."""
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
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        recipe = json.loads((ROOT / entry["fixture_recipe"]).read_text())
        old_source = recipe["generator"]["source"]
        spec = json.loads((ROOT / old_source).read_text())
        if len(spec["graphs"]) != 240:
            raise ValueError("Expected 240 source graphs")
        for graph in spec["graphs"]:
            if not graph["path"].endswith(".pkl"):
                raise ValueError("Unexpected graph format")
            graph["path"] = graph["path"][:-4] + ".adapter.json"
        frame_path = "capture/native/frames.jsonl"
        frames = [json.loads(row) for row in spec["files"][frame_path].splitlines()]
        if len(frames) != 240:
            raise ValueError("Expected 240 frame-map rows")
        for row in frames:
            row["base"] = row["base"].replace(".pkl", ".adapter.json")
            if "abstract" in row:
                row["abstract"] = row["abstract"].replace(".pkl", ".adapter.json")
            row["adapter_graph"] = row["base"]
        spec["files"][frame_path] = "\n".join(json.dumps(row) for row in frames) + "\n"
        new_spec = HERE / f"update700-{suffix}-diagnostic.json"
        save(new_spec, spec)
        new_source = new_spec.relative_to(ROOT).as_posix()
        recipe["generator"] = {"source": new_source, "sha256": sha(new_spec)}
        for source in recipe["sources"]:
            if source["source"] == old_source:
                source["source"] = new_source
                source["sha256"] = sha(new_spec)
        new_recipe = HERE / f"update700-{suffix}-diagnostic-recipe.json"
        save(new_recipe, recipe)
        entry["fixture_recipe"] = new_recipe.relative_to(ROOT).as_posix()
        print(json.dumps({"case": suffix, "graphs": len(spec["graphs"]), "spec_sha256": sha(new_spec)}))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
