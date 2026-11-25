"""Author an isolated exact towing construction draft without changing selected receipts."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
ASSIGNMENT = PACKAGE.name
CASE_ID = ASSIGNMENT + '__towed_entrant_can_occupy_gap'


def serialize(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def build():
    baseline = json.loads((PACKAGE / 'cases/entrant_can_occupy_gap-construction.json').read_text())
    baseline['case_id'] = CASE_ID
    baseline['entrypoint'] = 'runner.py'
    baseline['status'] = 'diagnostic_draft'
    baseline['mechanisms']['drawn_unit'] = 'reviewed unpowered prop attached behind first caravan vehicle'
    baseline['mechanisms']['note'] = 'Towing candidate remains unselected pending saved finalizer and Native review.'
    files = baseline['files']
    config_file = next(item for item in files if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['selected_case_id'] = CASE_ID
    config['supported_case_ids'] = [CASE_ID]
    config['case']['case_id'] = CASE_ID
    config_file['content'] = serialize(config)
    packet_file = next(item for item in files if item['path'] == 'site_packet.json')
    packet = json.loads(packet_file['content'])
    packet['drawn_unit'] = {
        'drawn_unit_review_status': 'diagnostic_unreviewed',
        'blueprint_id': 'static.prop.diagnostic_trailer',
        'drawn_unit_has_motive_power': False,
        'mesh_review_basis': 'Diagnostic placeholder pending original Native mesh review',
        'relative_transform': {'x': -4, 'y': 0, 'z': .5, 'yaw_deg': 0}}
    design = 'Diagnostic towing mesh and attachment placeholder; not an original Native review.\n'
    packet['towing_design_source'] = {'path': 'towing_design_source.txt',
                                      'sha256': hashlib.sha256(design.encode()).hexdigest()}
    packet_file['content'] = serialize(packet)
    files.append({'path': 'towing_design_source.txt', 'content': design})
    for name in ('caravan_towing_native.py', 'caravan_combination_native.py',
                 'caravan_combination_capture.py', 'caravan_combination.py'):
        files.append({'path': name, 'source': str((PACKAGE / name).relative_to(REPO)),
                      'content': (PACKAGE / name).read_text()})
    runner = next(item for item in files if item['path'] == 'runner.py')
    runner['source'] = str((PACKAGE / 'caravan_towing_native.py').relative_to(REPO))
    runner['content'] = (PACKAGE / 'caravan_towing_native.py').read_text()
    test = next(item for item in files if item['path'] == 'tests/test_offline.py')
    test['content'] = test['content'].replace('import caravan_native as native',
                                            'import caravan_towing_native as native')
    test['content'] = test['content'].replace(ASSIGNMENT + '__entrant_can_occupy_gap', CASE_ID)
    path = PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json'
    path.write_text(serialize(baseline))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
                'cases': [{'case_id': CASE_ID, 'kind': 'diagnostic',
                           'construction': path.name,
                           'construction_sha256': digest}], 'comparisons': []}
    manifest_path = PACKAGE / 'cases/towing-diagnostic-manifest.json'
    manifest_path.write_text(serialize(manifest))
    print(json.dumps({'case_id': CASE_ID, 'construction_sha256': digest,
                      'manifest': str(manifest_path.relative_to(REPO))}))


if __name__ == '__main__':
    build()
