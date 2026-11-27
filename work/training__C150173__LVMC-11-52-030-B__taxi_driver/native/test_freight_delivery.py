"""Structural original-source freight audit tests using declared synthetic data."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from freight_delivery_audit import audit, sha
from freight_finalize import SOURCES, source_measurement
from freight_seal_review import seal

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare(folder, suffix):
    source = SCRATCH / f'selected-fixture-{suffix}-v21'
    shutil.copytree(source, folder, dirs_exist_ok=True)
    construction = json.loads((PACKAGE / 'native-selected' / suffix / 'construction.json').read_text())
    for item in construction['files']:
        path = folder / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    write(folder / 'construction.json', construction)
    config = json.loads((folder / 'config.json').read_text())
    for name in ('freight-native.jsonl', 'trace.jsonl'):
        path = folder / name
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row['source_kind'] = 'original_native'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    refs = {
        'commercial-status-review.json': ('freight-native.jsonl', 'overview.mkv'),
        'sign-review.json': ('yellow-freight-road.xodr', 'reference_corner.mkv'),
        'freight-purpose-review.json': ('freight-native.jsonl', 'approach.mkv')}
    for name, paths in refs.items():
        path = folder / name
        review = json.loads(path.read_text())
        review['source_kind'] = 'original_native'
        review.pop('synthetic_cpu_fixture', None)
        review['source_refs'] = {rel: sha(folder / rel) for rel in paths}
        if name == 'commercial-status-review.json':
            review['observed_commercial_use'] = True
        else:
            review['source_pixels'] = [{'camera': 'reference_corner',
                'video_frame': 250, 'video_sha256': sha(folder / 'reference_corner.mkv'),
                'observed_visible': True,
                'observation': 'Fabricated structural-test pixel observation'}]
        write(path, review)
    manifest = folder / 'source-manifest.json'
    if manifest.exists():
        manifest.unlink()
    write(folder / 'capture-seal.json', {'provenance_kind': 'native',
        'diagnostic_fixture': False, 'frames': 600,
        'sources': {name: sha(folder / name) for name in SOURCES}})
    seal(folder)
    measured = source_measurement(folder)
    write(folder / 'result.json', {'case_id': config['case_id'], 'measured_values': measured})
    write(folder / 'analysis-report.json', {'measurements': {
        'freight_yellow_zone_measurement': {'value': measured}}})
    return config['case_id']


def run(case, negative_pixels=False):
    suffix = case.rsplit('__', 1)[1]
    if case != PACKAGE.name + '__' + suffix or suffix not in ('freight_load', 'freight_unload', 'freight_wait'):
        raise ValueError('Unknown exact freight test case')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c150173-freight-delivery-') as temporary:
        folder = Path(temporary)
        prepare(folder, suffix)
        if negative_pixels:
            path = folder / 'sign-review.json'
            review = json.loads(path.read_text())
            review['source_pixels'][0]['video_sha256'] = '0' * 64
            write(path, review)
            write(folder / 'capture-seal.json', {'provenance_kind': 'native',
                'diagnostic_fixture': False, 'frames': 600,
                'sources': {name: sha(folder / name) for name in SOURCES}})
            (folder / 'source-manifest.json').unlink()
            seal(folder)
            measured = source_measurement(folder)
            write(folder / 'result.json', {'case_id': case, 'measured_values': measured})
            write(folder / 'analysis-report.json', {'measurements': {
                'freight_yellow_zone_measurement': {'value': measured}}})
        def fake_decode(path, dimensions):
            return {'frames': 600, 'width': dimensions[0],
                    'height': dimensions[1], 'sha256': sha(path)}
        with patch('audit_freight_original.decode', side_effect=fake_decode):
            report = audit(folder, case, diagnostic_test=True)
        if report['eligible_for_local_acceptance'] or not all(report['checks'].values()):
            raise ValueError('Freight structural audit changed')
        return {'case_id': case, 'diagnostic_only': True, 'checks': sorted(report['checks'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative-pixels', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.negative_pixels), sort_keys=True))
