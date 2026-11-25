"""Test pinned Native closure and saved-owner handoff on a synthetic fixture."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    repo = ROOT.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('scratch must be under .runtime-work')
    suffix = args.case.removeprefix(ROOT.name + '__')
    if ROOT.name + '__' + suffix != args.case or not (ROOT / 'cases' / suffix).is_dir():
        raise ValueError('foreign exact case')
    construction = json.loads((ROOT / 'cases' / suffix / 'delivery-construction.draft.json').read_text())
    stage = args.scratch / (suffix + '-lifecycle')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    prior = args.scratch / (suffix + '-complete_motion')
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(prior / name, stage / name)
    (stage / 'construction.json').write_text(json.dumps(construction) + '\n')
    (stage / 'runner.py').write_text(next(item['content'] for item in construction['files']
                                          if item['path'] == 'runner.py'))
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (
        record_native_exit, acknowledge_owner_release, _closure)
    seal = seal_capture(stage, frames=900, restoration={'restored': True},
                        errors=[], encoder_exit_codes={'diagnostic': 0})
    owner = args.scratch / (suffix + '-owner-release.json')
    if owner.exists():
        owner.unlink()
    try:
        acknowledge_owner_release(stage, owner, True)
    except ValueError:
        pass
    else:
        raise ValueError('premature owner release accepted')
    record_native_exit(stage)
    acknowledge_owner_release(stage, owner, True)
    _closure(stage, owner, 'synthetic_fixture', True)
    events = seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']
    print(json.dumps({'case_id': args.case, 'events': events,
                      'premature_owner_release_rejected': True,
                      'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
