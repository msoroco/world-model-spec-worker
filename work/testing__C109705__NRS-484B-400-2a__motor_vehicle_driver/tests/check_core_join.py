"""Reproduce the diagnostic packet check against the pinned Core join verifier."""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if ROOT / '.runtime-work' not in OUTPUT_ROOT.parents:
    raise ValueError('Core output root must be under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_native_capture import FakeAdapter, packet, CASE
from native_capture import capture
from core_packet import project
from traffic_spec_adapter.adapter import verify_join


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    scratch = ROOT / '.runtime-work/c109705-core-join-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        root = Path(temporary)
        survey = root / 'survey.json'
        packet(survey)
        capture(FakeAdapter(), CASE, survey, root / 'attempt')
        receipt = project(root / 'attempt', root / 'core')
        trace = rows(root / 'core/trace.jsonl')
        evidence = rows(root / 'core/capture/evidence.jsonl')
        frames = rows(root / 'core/capture/native/frames.jsonl')
        original, replay = verify_join(evidence, trace, frames, diagnostic_fixture=True)
        assert len(original) == len(replay) == receipt['frames'] == 900
        print('Core verify_join passed: 900 source-hashed diagnostic frames; '
              'graph capture and full conversion still required')


if __name__ == '__main__':
    main()
