"""Exercise pinned synthetic capture closure and saved processing ordering."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    repo = base.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('Scratch must be under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure
    suffix = args.case.removeprefix(base.name + '__')
    manifest = json.loads((base / 'execution-manifest.json').read_text())
    entry = next((e for e in manifest['cases'] if e['case_id'] == args.case), None)
    if entry is None or suffix not in ('maintain_clearance', 'cross_rider_path',
                                       'electric_bicycle__maintain_clearance', 'electric_bicycle__cross_rider_path',
                                       'electric_scooter__maintain_clearance', 'electric_scooter__cross_rider_path'):
        raise ValueError('Foreign exact case')
    construction = json.loads((base / entry['construction']).read_text())
    stage = args.scratch / (suffix + '-lifecycle')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    source = args.scratch / (suffix + '-complete_motion')
    for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(source / name, stage / name)
    (stage / 'construction.json').write_text(json.dumps(construction) + '\n')
    (stage / 'runner.py').write_text(next(f['content'] for f in construction['files'] if f['path'] == 'runner.py'))
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    seal = seal_capture(stage, frames=900, restoration={'restored': True},
                        errors=[], encoder_exit_codes={'diagnostic': 0})
    if seal['events'] != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Seal lifecycle differs')
    try:
        acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    except ValueError:
        pass
    else:
        raise ValueError('Premature owner release accepted')
    record_native_exit(stage)
    acknowledge_owner_release(stage, stage / 'owner-release.json', True)
    _closure(stage, stage / 'owner-release.json', 'synthetic_fixture', True)
    events = seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']
    print(json.dumps({'case_id': args.case, 'events': events,
                      'premature_owner_release_rejected': True,
                      'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
