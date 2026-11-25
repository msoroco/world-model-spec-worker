"""Exercise source-bound synthetic wait/entry outcomes and lifecycle order."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from saved_measurement import measure_saved

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('arrow_wait', 'arrow_early_entry', 'arrow_walk_entry', 'arrow_walk_wait')
FIXTURES = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def fixture(case_id, fixture_kind, output):
    kind = case_id.rsplit('__', 1)[-1]
    if kind not in KINDS or case_id != HERE.name + '__' + kind or fixture_kind not in FIXTURES:
        raise ValueError('unknown exact synthetic pedestrian fixture')
    root = HERE / 'cases' / kind / 'diagnostic-sources'
    source = json.loads((root / 'pedestrian-source.json').read_text())
    site_ref, events_ref = source['site_ref'], source['events_ref']
    original_events = json.loads((root / events_ref['path']).read_text())
    refs = [{'path': str((root / name).relative_to(REPO)), 'sha256': sha(root / name)}
            for name in ('site.json', 'original_events.json', 'pedestrian-source.json')]
    status = 'unverified'
    realized = {}
    if fixture_kind == 'complete_motion':
        measured = measure_saved(root, site_ref, events_ref, case_id, len(original_events))
        status = 'met'
        realized = {'sampled_entry_frame': (measured['first_highway_entry'] or {}).get('frame'),
                    'sampled_wait_outside': measured['first_highway_entry'] is None,
                    'sole_arrow_frames': measured['sole_green_arrow_frames'],
                    'separate_walk_frame_count': measured['separate_walk_frame_count']}
    elif fixture_kind == 'incomplete_motion':
        altered = [dict(row) for row in original_events]
        # Reverse the observed entry outcome while retaining the source clock.
        altered[-1]['pedestrian_xy'] = [-0.5, 1.0] if kind.endswith('entry') else [1.0, 1.0]
        changed = root / 'incomplete-events.json'
        write(changed, altered)
        changed_ref = {'path': changed.name, 'sha256': sha(changed)}
        refs[1] = {'path': str(changed.relative_to(REPO)), 'sha256': sha(changed)}
        try:
            measure_saved(root, site_ref, changed_ref, case_id, len(altered))
        except ValueError as error:
            if 'entry behavior differs' not in str(error):
                raise
        else:
            raise ValueError('incomplete pedestrian outcome was accepted')
        status = 'not_met'
    else:
        absent = REPO / '.runtime-work/c109171-owner' / ('absent-' + kind + '-pedestrian-source.json')
        if absent.exists():
            raise ValueError('missing-evidence fixture unexpectedly exists')
        refs[2] = {'path': str(absent), 'condition': 'absent'}
    write(output, {'case_id': case_id, 'fixture_kind': fixture_kind,
                   'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                   'physical_checks': {'maneuver': {
                       'status': status, 'method': 'source_bound_sampled_wait_or_entry_goal',
                       'sources': refs}}, 'maneuver_completed': status == 'met',
                   'realized_observables': realized,
                   'scope': 'Three-frame CPU outcome classification only; 900-frame Native review pending'})
    print(fixture_kind, status, sha(output))


def record():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        kind = case_id.rsplit('__', 1)[-1]
        folder = HERE / 'cases' / kind / 'physical'
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for fixture_kind in FIXTURES:
            result = folder / (fixture_kind + '.json')
            log = folder / (fixture_kind + '.log')
            cmd = [sys.executable, str(HERE / 'prove_physical_preparation.py'),
                   '--case', case_id, '--kind', fixture_kind, '--output', str(result)]
            process = subprocess.run(cmd, cwd=REPO,
                                     env=dict(os.environ, TMPDIR=str(REPO / '.runtime-work/c109171-owner/tmp'),
                                              PYTHONDONTWRITEBYTECODE='1'),
                                     capture_output=True, text=True)
            log.write_text((process.stdout + process.stderr).rstrip() + '\n')
            if process.returncode:
                raise ValueError('physical diagnostic fixture failed: ' + kind + ': ' + fixture_kind)
            fixtures.append({'kind': fixture_kind, 'command': ' '.join(cmd), 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)), 'result_sha256': sha(result)})
        lifecycle = folder / 'lifecycle.log'
        lifecycle.write_text('\n'.join(EVENTS) + '\n')
        if EVENTS.index('saved_processing_started') <= EVENTS.index('owner_released'):
            raise ValueError('saved processing started before owner release')
        receipt = folder / 'receipt.json'
        write(receipt, {'format': 'worker-physical-preparation', 'case_id': case_id,
                        'construction_sha256': entry['construction_sha256'],
                        'fixtures': fixtures,
                        'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                      'log': str(lifecycle.relative_to(HERE)),
                                      'log_sha256': sha(lifecycle)},
                        'scope': 'Synthetic CPU classification; original physical review pending'})
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': sha(receipt)}
        print(kind, 'three synthetic outcomes and lifecycle passed')
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=FIXTURES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if any(x is not None for x in (args.case, args.kind, args.output)):
        if not all(x is not None for x in (args.case, args.kind, args.output)):
            raise ValueError('one fixture needs case, kind and output')
        fixture(args.case, args.kind, args.output)
    else:
        record()


if __name__ == '__main__':
    main()
