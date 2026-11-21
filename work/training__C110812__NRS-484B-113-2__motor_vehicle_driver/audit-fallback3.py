"""Check the repaired third alternative against fixed cameras and source triggers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(bundle):
    return json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))


def audit():
    entries = read(HERE / 'control-proof-manifest.json')['cases']
    rows = []
    for entry in entries:
        candidate = next(c for c in entry['candidates'] if c['id'] == 'fallback3')
        primary = read(HERE / entry['construction'])
        path = HERE / candidate['construction']
        if sha(path) != candidate['construction_sha256']:
            raise ValueError('Fallback 3 construction hash changed')
        fallback = read(path)
        base, changed = config(primary), config(fallback)
        if (base['cameras'] != changed['cameras'] or base['duration_s'] != changed['duration_s']
                or base['rate_hz'] != changed['rate_hz'] or base['case_id'] != changed['case_id']
                or changed['engineering_knobs']['target_reverse_speed_m_s'] != 0.7
                or candidate['changed_knobs'] != ['target_reverse_speed_m_s']
                or candidate['trigger']['metric'] != 'max_reverse_heading_rate_deg_s'):
            raise ValueError('Fallback 3 camera/control contract differs')
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            files = {item['path']: item['content'] for item in fallback['files']}
            for name in ('engineering.py', 'controller.py', 'geometry.py', 'road.xodr'):
                (temp / name).write_text(files[name])
            sys.path.insert(0, directory)
            try:
                for name in ('engineering', 'controller', 'geometry'):
                    sys.modules.pop(name, None)
                import engineering
                suffix = changed['case_suffix']
                knobs = engineering.controller_parameters(suffix, 'fallback3')
                if knobs.target_reverse_speed_m_s != 0.7:
                    raise ValueError('Fallback 3 does not change controller speed')
                metric = candidate['trigger']['metric']
                for value, expected in ((13, True), (11, False)):
                    source = temp / 'metrics.json'
                    source.write_text(json.dumps({'source_kind': 'original_native_and_video', metric: value}))
                    if engineering.evaluate_trigger('fallback3', source, sha(source)) is not expected:
                        raise ValueError('Fallback 3 trigger boundary differs')
                    try:
                        engineering.evaluate_trigger('fallback3', source, '0' * 64)
                    except ValueError as error:
                        if 'hash differs' not in str(error):
                            raise
                    else:
                        raise ValueError('Fallback 3 accepts changed source hash')
            finally:
                sys.path.remove(directory)
                for name in ('engineering', 'controller', 'geometry'):
                    sys.modules.pop(name, None)
        rows.append({'case_id': entry['case_id'], 'construction_sha256': candidate['construction_sha256'],
                     'fixed_cameras': True, 'target_reverse_speed_m_s': 0.7,
                     'trigger_positive_negative_hash_rejection': True})
    return {'passed': True, 'rows': rows, 'scope': 'CPU fallback source checks; Native trigger unobserved'}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
