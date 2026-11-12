"""Exercise exact distinct-case motion classifier and saved ownership lifecycle."""

import argparse
import json

from build_physical_proofs import HERE, run_one


def main(name):
    manifest = "diagnostic-" + name + "-manifest.json"
    case_id = json.loads((HERE / manifest).read_text())["cases"][0]["case_id"]
    saved = name + "-branch-processing.json"
    feature, rest = case_id.removeprefix(HERE.name + "__").split("__", 1)
    probe = rest.split("__", 1)[0]
    run_one(name, feature, probe, manifest, saved, case_id=case_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    main(args.name)
