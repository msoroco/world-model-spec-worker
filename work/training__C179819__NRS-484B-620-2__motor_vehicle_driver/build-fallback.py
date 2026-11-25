"""Create common controller-gain fallback for each linked speed case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "draft-execution-manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        source = json.loads((HERE / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(source))
        controller = next(item for item in fallback["files"] if item["path"] == "controller.py")
        assert controller["content"].count("error * 0.08") == 2
        controller["content"] = controller["content"].replace("error * 0.08", "error * 0.10")
        config = next(item for item in fallback["files"] if item["path"] == "config.json")
        value = json.loads(config["content"])
        value["candidate_id"] = "fallback1"
        config["content"] = json.dumps(value, indent=2) + "\n"
        fallback["mechanisms"] = ["Same roadway, speed request, cameras and capture; controller error gain 0.10 instead of 0.08."]
        suffix = entry["case_id"].split("__")[-1]
        path = HERE / "draft-exact" / suffix / "fallback1/construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + "\n")
        entry["candidates"] = [{"id": "fallback1", "construction": str(path.relative_to(HERE)),
            "construction_sha256": digest(path),
            "trigger": {"source": "original Native actor-poses.jsonl and result.json",
                "metric": "frames within one mph of the unchanged speed request",
                "failure_condition": "fewer than 500 of 600 original samples within one mph, after checking no original source loss"},
            "changed_knobs": ["controller proportional speed-error gain 0.08 to 0.10 for throttle and brake"]}]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print({entry["case_id"]: entry["candidates"][0]["construction_sha256"] for entry in manifest["cases"]})


if __name__ == "__main__":
    main()
