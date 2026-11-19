"""Preserve each authored fallback's capture identity under JSON graph diagnostics."""
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
    base = json.loads((HERE / "execution-manifest.json").read_text())
    for selected in base["cases"]:
        suffix = selected["case_id"].removeprefix(HERE.name + "__")
        for fallback in selected["candidates"]:
            name = fallback["id"]
            recipe = json.loads((HERE / "selected-diagnostics" / suffix / f"{name}-recipe.json").read_text())
            old_source = recipe["generator"]["source"]
            spec = json.loads((ROOT / old_source).read_text())
            if len(spec["graphs"]) != 240:
                raise ValueError("Unexpected frame count")
            for graph in spec["graphs"]:
                if not graph["path"].endswith(".pkl"):
                    raise ValueError("Unexpected graph format")
                graph["path"] = graph["path"][:-4] + ".adapter.json"
            frame_path = "capture/native/frames.jsonl"
            frames = [json.loads(line) for line in spec["files"][frame_path].splitlines()]
            if len(frames) != 240:
                raise ValueError("Unexpected frame map length")
            for frame in frames:
                frame["base"] = frame["base"].replace(".pkl", ".adapter.json")
                if "abstract" in frame:
                    frame["abstract"] = frame["abstract"].replace(".pkl", ".adapter.json")
                frame["adapter_graph"] = frame["base"]
            spec["files"][frame_path] = "\n".join(json.dumps(frame) for frame in frames) + "\n"
            spec_path = HERE / f"update801-{suffix}-{name}-diagnostic.json"
            save(spec_path, spec)
            new_source = spec_path.relative_to(ROOT).as_posix()
            recipe["generator"] = {"source": new_source, "sha256": sha(spec_path)}
            for source in recipe["sources"]:
                if source["source"] == old_source:
                    source["source"] = new_source
                    source["sha256"] = sha(spec_path)
            recipe_path = HERE / f"update801-{suffix}-{name}-diagnostic-recipe.json"
            save(recipe_path, recipe)
            candidate_manifest = json.loads(json.dumps(base))
            entry = next(entry for entry in candidate_manifest["cases"] if entry["case_id"] == selected["case_id"])
            entry["fixture_recipe"] = recipe_path.relative_to(ROOT).as_posix()
            candidate_path = HERE / f"update801-{suffix}-{name}-diagnostic-manifest.json"
            save(candidate_path, candidate_manifest)
            print(json.dumps({"case": suffix, "candidate": name, "manifest_sha256": sha(candidate_path)}))


if __name__ == "__main__":
    main()
