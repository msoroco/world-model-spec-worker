"""Construct the same three measured-risk controller alternatives for each other case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("at", "beyond", "crest-short", "crest-at", "crest-beyond")


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    reference = json.loads((HERE / "diagnostic-curve-short-fallback-manifest.json").read_text())
    definitions = reference["cases"][0]["candidates"]
    outputs = {}
    for suffix in SUFFIXES:
        primary = json.loads((HERE / ("construction-" + suffix + ".json")).read_text())
        manifest = json.loads((HERE / ("diagnostic-" + suffix + "-manifest.json")).read_text())
        candidates = []
        for definition in definitions:
            ident = definition["id"]
            runner_source = HERE / "generated-runners" / ("runner-" + ident + ".py")
            candidate = json.loads(json.dumps(primary))
            for row in candidate["files"]:
                if row["path"] == "runner.py":
                    row["content"] = runner_source.read_text()
                    row["source"] = str(runner_source.relative_to(REPO))
            candidate["candidate_engineering"] = {
                "id": ident, "changed_knob": definition["changed_knobs"][0],
                "reason": definition["trigger"]["failure_condition"]}
            target = HERE / ("construction-" + suffix + "-" + ident + ".json")
            dump(target, candidate)
            candidates.append({"id": ident, "construction": target.name,
                "construction_sha256": sha(target),
                "trigger": definition["trigger"],
                "changed_knobs": definition["changed_knobs"]})
        manifest["cases"][0]["candidates"] = candidates
        output = HERE / ("diagnostic-" + suffix + "-fallback-manifest.json")
        dump(output, manifest)
        outputs[suffix] = [row["construction_sha256"] for row in candidates]
    return outputs


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
