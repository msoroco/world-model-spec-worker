"""Give every exact selected config its own immutable work-owned source path."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    test = HERE / "tests/test_native_draft.py"
    for entry in manifest["cases"]:
        for candidate in [entry, *entry["candidates"]]:
            path = HERE / candidate["construction"]
            construction = json.loads(path.read_text())
            for file in construction["files"]:
                if file["path"] == "config.json":
                    source = path.parent / "config.json"
                    source.write_text(file["content"])
                    file["source"] = str(source.relative_to(ROOT))
                elif file["path"] == "tests/test_native_draft.py":
                    file["content"] = test.read_text()
                    file["source"] = str(test.relative_to(ROOT))
            save(path, construction)
            candidate["construction_sha256"] = sha(path)
    save(manifest_path, manifest)
    primary = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    save(HERE / "construction.json", primary)
    (HERE / "config.json").write_text(next(x["content"] for x in primary["files"]
                                           if x["path"] == "config.json"))
    print(json.dumps({"candidate_configs_materialized": 8,
                      "test_source_rebound": 8,
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
