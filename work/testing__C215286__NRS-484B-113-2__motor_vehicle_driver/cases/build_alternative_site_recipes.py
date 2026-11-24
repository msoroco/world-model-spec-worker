"""Return exact, hash-bound diagnostic site inputs for four alternatives.

These source-only recipes establish the package/fixture separation. Motion,
graphs and decoded camera sources must be added before compatibility proof.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def main():
    manifest = json.loads((ROOT / "alternative-offline-manifest.json").read_text())
    for index, entry in enumerate(manifest["cases"]):
        bundle = json.loads((ROOT / entry["construction"]).read_text())
        files = {item["path"]: item["content"] for item in bundle["files"]}
        config = json.loads(files["config.json"])
        site_name = config["site_packet"]
        site = json.loads(files["site_templates/" + site_name])
        names = [site_name]
        names.extend(site[key]["path"] for key in
                     ("geometry_source", "camera_source", "road_topology_source")
                     if site.get(key))
        directory = ROOT / "fixtures" / str(index)
        directory.mkdir(parents=True, exist_ok=True)
        sources = []
        for name in names:
            content = files["site_templates/" + name]
            destination = directory / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
            relative = destination.relative_to(REPO).as_posix()
            sources.append({"path": name, "source": relative,
                            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
        recipe = {"format": "worker-fixture-recipe", "sources": sources}
        (directory / "site-source-recipe.json").write_text(
            json.dumps(recipe, indent=2) + "\n")
        print(entry["case_id"], len(sources), "unshadowed site sources")


if __name__ == "__main__":
    main()
