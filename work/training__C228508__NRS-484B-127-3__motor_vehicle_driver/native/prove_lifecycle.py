"""Check pinned closure ordering on a synthetic diagnostic, without Native ownership claims."""

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.saved_processing import (
    _closure, acknowledge_owner_release, record_native_exit)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(case, scratch):
    if case not in ('probe_a', 'probe_b') or scratch.exists():
        raise ValueError('Select fresh exact synthetic fixture')
    scratch.mkdir(parents=True)
    source = REPO / '.runtime-work/c228508-compat' / (
        'v11-a-primary' if case == 'probe_a' else 'v13-probe_b-primary')
    shutil.copyfile(source / 'construction.json', scratch / 'construction.json')
    events = ['capture_finished', 'encoders_closed', 'restoration_verified']
    seal = {'events':list(reversed(events)), 'sources':{},
            'native_revision':{'construction_sha256':'synthetic-diagnostic-revision'},
            'diagnostic_fixture':True}
    write(scratch / 'capture-seal.json', seal)
    try:
        record_native_exit(scratch)
    except ValueError as error:
        if 'ordering' not in str(error):
            raise
    else:
        raise AssertionError('Out-of-order closure was accepted')
    seal['events'] = events
    write(scratch / 'capture-seal.json', seal)
    exit_record = record_native_exit(scratch)
    release = acknowledge_owner_release(scratch, scratch / 'owner-release.json', True)
    _closure(scratch, scratch / 'owner-release.json', 'synthetic_fixture', True)
    print(json.dumps({'case':case,'events':events + ['native_exit','owner_released',
                     'saved_processing_started'], 'out_of_order_rejected':True,
                     'exit_record_event':exit_record['event'],
                     'release_record_event':release['event'],
                     'actual_owner_release_claimed':False,
                     'synthetic_fixture':True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', required=True)
    options = parser.parse_args()
    run(options.case, Path(options.scratch).resolve())
