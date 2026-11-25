"""Build one source-bound selected fallback diagnostic without changing primary proofs."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(probe, candidate):
    if probe not in (1, 2) or candidate not in ("fallback1", "fallback2"):
        raise ValueError("Only the two crossing-preserving fallbacks are supported")
    prefix = f"selected-probe{probe}"
    fallback_prefix = f"{prefix}-{candidate}"
    source = (HERE / f"build-selected-probe{probe}.py").read_text()
    source = source.replace(f"drafts/probe_{probe}/primary", f"drafts/probe_{probe}/{candidate}")
    source = source.replace(prefix, fallback_prefix)
    source = source.replace(f"c109137-selected-probe{probe}-source",
                            f"c109137-selected-probe{probe}-{candidate}-source")
    namespace = {"__name__": "selected_fallback_builder", "__file__": str(HERE / f"build-selected-probe{probe}.py")}
    exec(compile(source, str(HERE / f"build-selected-probe{probe}.py"), "exec"), namespace)
    namespace["main"]()
    path = HERE / f"{fallback_prefix}-manifest.json"
    manifest = json.loads(path.read_text())
    entry = manifest["cases"][0]
    fallback_construction = entry["construction"]
    fallback_sha = entry["construction_sha256"]
    primary_path = HERE / f"{prefix}-construction.json"
    entry["construction"] = primary_path.name
    entry["construction_sha256"] = sha(primary_path)
    entry["candidates"] = [{"id": candidate,
                             "construction": fallback_construction,
                             "construction_sha256": fallback_sha,
                             "trigger": {"source": "saved Native source review",
                                         "metric": "signal lead or stripe visibility",
                                         "failure_condition": "primary source review requires physical fallback"},
                             "changed_knobs": ["requested crossing speed" if candidate == "fallback1"
                                               else "overview camera pose"]}]
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"probe": probe, "candidate": candidate,
                      "manifest": path.name, "manifest_sha256": sha(path),
                      "fallback_construction_sha256": fallback_sha}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=int, required=True)
    parser.add_argument("--candidate", choices=("fallback1", "fallback2"), required=True)
    args = parser.parse_args()
    main(args.probe, args.candidate)
