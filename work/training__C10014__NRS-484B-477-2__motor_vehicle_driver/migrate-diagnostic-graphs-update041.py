"""Make new diagnostic sources for the pinned JSON graph adapter."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for suffix in ("reference", "contrast"):
        old_spec = HERE / f"update015-diagnostic-{suffix}.json"
        new_spec = HERE / f"update041-diagnostic-{suffix}.json"
        old_recipe = HERE / f"update015-diagnostic-{suffix}-recipe.json"
        new_recipe = HERE / f"update041-diagnostic-{suffix}-recipe.json"
        if new_spec.exists() or new_recipe.exists():
            raise FileExistsError("Retain prior update041 diagnostic sources")
        spec = json.loads(old_spec.read_text())
        for graph in spec["graphs"]:
            if not graph["path"].endswith(".pkl"):
                raise ValueError("Unexpected old graph path")
            graph["path"] = graph["path"][:-4] + ".adapter.json"
        frames = spec["files"]["capture/native/frames.jsonl"]
        if frames.count(".pkl") != 960:
            raise ValueError("Expected two graph paths for each of 480 frames")
        rows = [json.loads(line) for line in frames.splitlines()]
        for row in rows:
            row["base"] = row["base"].replace(".pkl", ".adapter.json")
            row["abstract"] = row["abstract"].replace(".pkl", ".adapter.json")
            row["adapter_graph"] = row["base"]
        spec["files"]["capture/native/frames.jsonl"] = "\n".join(
            json.dumps(row) for row in rows) + "\n"
        write(new_spec, spec)
        recipe = json.loads(old_recipe.read_text())
        relative = str(new_spec.relative_to(ROOT))
        recipe["generator"] = {"source": relative, "sha256": sha(new_spec)}
        for source in recipe["sources"]:
            if source["source"] == str(old_spec.relative_to(ROOT)):
                source["source"] = relative
                source["sha256"] = sha(new_spec)
        write(new_recipe, recipe)
        entry = next(e for e in manifest["cases"] if e["case_id"].endswith("__" + suffix))
        entry["fixture_recipe"] = str(new_recipe.relative_to(ROOT))
        print(json.dumps({"case": suffix, "graphs": len(spec["graphs"]),
                          "spec_sha256": sha(new_spec), "recipe_sha256": sha(new_recipe)}))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
