"""Exercise exact saved-only driveway processing on synthetic source packets."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--manifest", default=str(ROOT / "execution-manifest.draft.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    from worker_exchange.common import read, sha, within, write
    from worker_exchange.candidate_constructions import select
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.saved_processing import run

    manifest = Path(args.manifest).resolve()
    entry, selected, construction = select(manifest, args.case, args.candidate)
    output = Path(args.output).resolve()
    if REPO / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("fresh .runtime-work saved output required")
    output.mkdir(parents=True)
    attempt = output / "attempt"
    attempt.mkdir()
    for item in construction["files"]:
        target = within(attempt, item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"], encoding="utf-8")
    write(attempt / "construction.json", construction)
    if args.candidate != "primary":
        write(attempt / "candidate-selection.json", {
            "format": "worker-candidate-selection", "case_id": args.case,
            "candidate_id": selected["id"],
            "construction_sha256": selected["construction_sha256"],
            "manifest_sha256": sha(manifest),
        })
    with tempfile.TemporaryDirectory(prefix="fixture-", dir=output) as temporary:
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
    receipt = run(manifest, args.case, attempt, output / "derived",
                  args.library, args.validator)
    if (receipt.get("passed"), receipt.get("recorded_only"),
            receipt.get("candidate_id"), receipt.get("missing_evidence")) != (
                True, True, args.candidate, False):
        raise ValueError("saved-only selected driveway processing incomplete")
    print(json.dumps({"case_id": args.case, "candidate_id": args.candidate,
                      "saved_only": True, "passed": True,
                      "result_sha256": receipt["result_sha256"],
                      "final_video_checks": receipt["final_video_checks"] is not None},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
