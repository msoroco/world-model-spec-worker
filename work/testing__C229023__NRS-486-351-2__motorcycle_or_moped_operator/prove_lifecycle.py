"""Exercise the ordered capture closure protocol with a synthetic source set."""

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
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    if repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('Lifecycle scratch belongs under .runtime-work')
    suffix = args.case.removeprefix(root.name + '__')
    if args.case != root.name + '__' + suffix:
        raise ValueError('Foreign exact case')
    construction = json.loads(((root / 'construction.json' if suffix == 'same_lane_pass' else root / 'cases' / suffix / 'construction.json')).read_text())
    if construction['case_id'] != args.case:
        raise ValueError('Construction identity differs')
    stage = args.scratch.resolve() / ('lifecycle-' + suffix)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / 'construction.json').write_text(json.dumps(construction) + '\n')
    for item in construction['files']:
        if item['path'] in ('runner.py', 'config.json'):
            (stage / item['path']).write_text(item['content'])
    (stage / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
    (stage / 'trace.jsonl').write_text(json.dumps({'frame': 38033, 'time_s': 0.05}) + '\n')
    (stage / 'video_frames.jsonl').write_text(json.dumps({
        'video_frame': 0, 'carla_frame': 38033, 'time_s': 0.05}) + '\n')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
                                                  acknowledge_owner_release, _closure)
    seal = seal_capture(stage, frames=1, restoration={'restored': True},
                        errors=[], encoder_exit_codes={'overview': 0})
    native_exit = record_native_exit(stage)
    owner = stage / 'owner-release.json'
    release = acknowledge_owner_release(stage, owner, True)
    _closure(stage, owner, 'native', False)
    if seal['events'] != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Capture was not closed in order')
    if native_exit['event'] != 'native_exit' or release['event'] != 'owner_released':
        raise ValueError('Native exit or owner release absent')
    try:
        _closure(stage, None, 'native', False)
    except ValueError as error:
        if 'owner-release receipt' not in str(error):
            raise
    else:
        raise ValueError('Missing owner release was accepted')
    print(json.dumps({'case_id': args.case,
                      'events': seal['events'] + ['native_exit', 'owner_released',
                                                  'saved_processing_started'],
                      'missing_owner_release_rejected': True,
                      'scope': 'synthetic lifecycle protocol test only'}))


if __name__ == '__main__':
    main()
