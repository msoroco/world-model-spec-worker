"""Synthetic structural tests for independent original delivery audit only."""
import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from audit_original import VIEWS
from delivery_audit import audit, sha, read
from finalize_original import SOURCES, inspect
from prove_physical import source_fixture, write
from seal_review import seal


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]


def prepare(folder, suffix):
    config, _ = source_fixture(folder, suffix)
    for name in ('yellow-zone-native.jsonl', 'observed-passenger-activity.jsonl',
                 'trace.jsonl'):
        path = folder / name
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row['source_kind'] = 'original_native'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    for name in ('taxicab-review.json', 'commercial-status-review.json', 'sign-review.json',
                 'passenger-purpose-review.json', 'ordinary-rules-review.json'):
        path = folder / name
        review = read(path)
        review['source_kind'] = 'original_native'
        review.pop('synthetic_cpu_fixture', None)
        if name == 'commercial-status-review.json':
            review['source_refs'] = {
                'yellow-zone-native.jsonl': sha(folder / 'yellow-zone-native.jsonl'),
                'overview.mkv': sha(folder / 'overview.mkv')}
        if name != 'ordinary-rules-review.json':
            review['source_pixels'] = [{
                'camera': 'reference_corner', 'video_frame': 250,
                'video_sha256': sha(folder / 'reference_corner.mkv'),
                'observed_visible': True,
                'observation': 'Fabricated test observation, not real pixels'}]
        write(path, review)
    write(folder / 'capture-seal.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'frames': 600, 'sources': {name: sha(folder / name) for name in SOURCES}})
    seal(folder)
    measured = inspect(folder, folder / 'source-manifest.json', 'original_native')
    write(folder / 'result.json', {'case_id': config['case_id'],
                                  'measured_values': measured})
    write(folder / 'analysis-report.json', {'measurements': {
        'taxi_yellow_zone_measurement': {'value': measured}}})
    return config['case_id']


def run(case_id, negative=False, negative_pixels=False):
    suffix = case_id.rsplit('__', 1)[1]
    if (case_id != PACKAGE.name + '__' + suffix or suffix not in
            ('probe_a', 'probe_b', 'probe_c', 'probe_d')):
        raise ValueError('Unknown exact taxi test case')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c150173-delivery-') as temporary:
        folder = Path(temporary)
        prepare(folder, suffix)
        if negative:
            (folder / 'sign-review.json').unlink()
        if negative_pixels:
            review = read(folder / 'sign-review.json')
            review['source_pixels'][0]['video_sha256'] = '0' * 64
            write(folder / 'sign-review.json', review)
            write(folder / 'capture-seal.json', {
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'frames': 600, 'sources': {name: sha(folder / name) for name in SOURCES}})
            (folder / 'source-manifest.json').unlink()
            seal(folder)
            measured = inspect(folder, folder / 'source-manifest.json', 'original_native')
            write(folder / 'result.json', {'case_id': case_id,
                                          'measured_values': measured})
            write(folder / 'analysis-report.json', {'measurements': {
                'taxi_yellow_zone_measurement': {'value': measured}}})
        def fake_decode(path, dimensions):
            return {'frames': 600, 'width': dimensions[0],
                    'height': dimensions[1], 'sha256': sha(path)}
        with patch('audit_original.decode', side_effect=fake_decode):
            report = audit(folder, case_id, diagnostic_test=True)
        if report['eligible_for_local_acceptance'] or not all(report['checks'].values()):
            raise ValueError('Synthetic delivery structural test changed')
        return {'case_id': case_id, 'diagnostic_only': True,
                'checks': sorted(report['checks'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--negative-pixels', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.negative, args.negative_pixels), sort_keys=True))
