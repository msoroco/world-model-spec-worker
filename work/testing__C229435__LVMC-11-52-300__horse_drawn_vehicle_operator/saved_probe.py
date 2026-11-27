"""Exercise exact saved-only processing on bounded source-bound diagnostics."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args(argv)
    from worker_exchange.common import read, within
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.saved_processing import run

    manifest_path = ROOT / "execution-manifest.json"
    entry = next(item for item in read(manifest_path)["cases"] if item["case_id"] == args.case)
    construction = read(ROOT / entry["construction"])
    output = Path(args.output).resolve()
    if REPO / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("fresh .runtime-work output required")
    output.mkdir(parents=True)
    attempt = output / "attempt"
    attempt.mkdir()
    for item in construction["files"]:
        target = within(attempt, item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    (attempt / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    with tempfile.TemporaryDirectory(dir=output, prefix="fixture-") as temporary:
        fixture = Path(temporary) / "sources"
        materialize(REPO, REPO / entry["fixture_recipe"], fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError("fixture shadows selected implementation")
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    receipt = run(manifest_path, args.case, attempt, output / "derived",
                  args.library, args.validator)
    if receipt.get("passed") is not True or receipt.get("recorded_only") is not True:
        raise ValueError("saved-only processing did not finish")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
