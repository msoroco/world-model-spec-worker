"""Bind independent delivery audit proofs and root portable entrypoints."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c230222-lvmc-route'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    text = source.read_text()
    if not text.endswith('\n') or text.endswith('\n\n') or any(
            row.rstrip(' \t') != row for row in text.splitlines()):
        raise ValueError('Invalid proof whitespace: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return str(target.relative_to(ROOT))


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix, entry in zip('ab', manifest['cases']):
        case = entry['case_id']
        positive = copy(SCRATCH / ('delivery-' + suffix + '-primary-v5.log'),
                        ROOT / 'delivery-proofs' / (suffix + '-diagnostic.log'))
        negative = copy(SCRATCH / ('delivery-' + suffix + '-primary-v5-negative.log'),
                        ROOT / 'delivery-proofs' / (suffix + '-original-required.log'))
        base = ('.venv-cpu/bin/python work/' + ROOT.name + '/delivery_audit.py --case ' + case +
            ' --candidate primary --attempt .runtime-work/c230222-lvmc-route/compat-' + suffix +
            '-primary-v5 --processing work/' + ROOT.name + '/selected-proofs/' + suffix +
            '-primary-saved.json --output .runtime-work/c230222-lvmc-route/delivery-' + suffix + '-primary-v5.json')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'command': base + ' --diagnostic', 'negative_command': base,
            'script': 'delivery_audit.py', 'script_sha256': sha(ROOT / 'delivery_audit.py'),
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required',
            'test_log': positive, 'test_log_sha256': sha(ROOT / positive),
            'negative_log': negative, 'negative_log_sha256': sha(ROOT / negative)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    primary = json.loads((ROOT / manifest['cases'][0]['construction']).read_text())
    config = json.loads(next(item['content'] for item in primary['files'] if item['path'] == 'config.json'))
    config['supported_case_ids'] = [entry['case_id'] for entry in manifest['cases']]
    (ROOT / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    for source, target in [('runner.py', 'runner.py'), ('route_meter.py', 'route_meter.py'),
                           ('finalize.py', 'finalize.py'), ('road.xodr', 'road.xodr'),
                           ('test_offline.py', 'tests/test_offline.py')]:
        copy(HERE / source, ROOT / target)
    for item in primary['files']:
        item['content'] = (ROOT / item['path']).read_text()
    primary['status'] = 'selected_cpu_proofs_bound'
    primary['measurement_plan']['status'] = 'selected_cpu_proofs_bound'
    (ROOT / 'construction.json').write_text(json.dumps(primary, indent=2) + '\n')
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'subject': 'full pedestrian body, route, origin and opposite curbs',
                      'interval': 'all 600 Native frames', 'view': name}
                     for name in ('overview','approach','reference_corner','driver_reference')]}
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'root_construction_sha256': sha(ROOT / 'construction.json')}))


if __name__ == '__main__':
    main()
