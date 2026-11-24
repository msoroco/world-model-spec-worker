"""Build exact source-bound final stopping-reference CPU requests."""
import hashlib
import json
from pathlib import Path

from route import requested_rows

HERE = Path(__file__).resolve().parent
CASE_DIR = HERE.parent
ROOT = CASE_DIR.parents[1]
SOURCE = ROOT / 'inputs' / CASE_DIR.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source = json.loads(SOURCE.read_text())
    if (source['cell']['cell_id'], source['cell']['layout'], source['cell']['control']) != (
            'C154537', 'one_way_to_one_way_intersection', 'inoperative_signal'):
        raise ValueError('Frozen cell differs')
    entries = []
    for suffix in ('controlled_1', 'controlled_2'):
        case_id = CASE_DIR.name + '__' + suffix
        request_path = HERE / ('request-' + suffix + '.jsonl')
        request_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                        for row in requested_rows(suffix)))
        config = {'case_id': case_id, 'case_suffix': suffix, 'cell_id': 'C154537',
                  'law_id': 'NRS-484B-250-4', 'actor': 'motor_vehicle_driver',
                  'assignment_sha256': sha(SOURCE), 'request_sha256': sha(request_path),
                  'law_text': source['law']['text'], 'rate_hz': 20, 'duration_s': 30,
                  'source_kind': 'synthetic_scene_request', 'native_observed': False,
                  'official_signal_authority_proven': False,
                  'driver_view_nearest_point_proven': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', SOURCE.read_text()),
            ('request.jsonl', request_path.read_text()),
            ('config.json', json.dumps(config, indent=2) + '\n'),
            ('route.py', (HERE / 'route.py').read_text()),
            ('check.py', (HERE / 'check.py').read_text()),
            ('tests/test_request.py', (HERE / 'tests/test_request.py').read_text()))]
        construction = {'case_id': case_id, 'cell_id': 'C154537',
            'law_id': 'NRS-484B-250-4', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'check.py', 'files': files,
            'recording_description': {'rate_hz': 20, 'duration_s': 30,
                'cameras_required': ['overview', 'ego_approach', 'cross_approach', 'driver_view'],
                'required_original_sources': ['Native motion', 'device-state history',
                    'stop-line and crosswalk survey', 'driver-view ray survey', 'four cameras'],
                'limitations': ['Request is synthetic and does not prove signal or view geometry']},
            'status': 'unselected_cpu_request_not_native_construction'}
        path = HERE / 'request-bundles' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case_id, 'construction': str(path.relative_to(CASE_DIR)),
            'construction_sha256': sha(path), 'candidates': [],
            'candidate_risk': {'status': 'physical',
                'reason': 'Native inoperative signal, nearest-view point and stop motion unproven'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE_DIR.name, 'status': 'partial', 'cases': entries,
                'original_native_observed': False, 'delivery_ready': False}
    (CASE_DIR / 'draft-request-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'construction_sha256':
                      [item['construction_sha256'] for item in entries]}))


if __name__ == '__main__':
    build()
