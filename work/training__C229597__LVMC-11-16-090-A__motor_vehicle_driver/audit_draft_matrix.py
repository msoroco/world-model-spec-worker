"""Independently check exact C229597 draft comparison and fallback identity."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
VIEWS = ['overview', 'approach', 'reference_corner', 'driver_reference']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def config(construction):
    return json.loads(next(x['content'] for x in construction['files']
                           if x['path'] == 'config.json'))


def main():
    manifest = read(P / 'draft-primary-manifest.json')
    proof = read(P / 'draft-offline-index.json')
    if (proof['manifest_sha256'] != sha(P / 'draft-primary-manifest.json')
            or len(manifest['cases']) != 2 or len(proof['records']) != 8):
        raise ValueError('Draft matrix identity differs')
    configs = {}
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        if case not in ('reference', 'contrast') or len(entry['candidates']) != 3:
            raise ValueError('Case or alternatives missing')
        for candidate in [dict(entry, id='primary'), *entry['candidates']]:
            ident = candidate['id']
            construction_path = P / candidate['construction']
            if sha(construction_path) != candidate['construction_sha256']:
                raise ValueError('Construction changed')
            cfg = config(read(construction_path))
            receipt = next((x for x in proof['records']
                            if x['case_id'] == entry['case_id']
                            and x['candidate_id'] == ident), None)
            if (receipt is None or receipt['construction_sha256'] != sha(construction_path)
                    or sha(P / receipt['offline_log']) != receipt['offline_log_sha256']
                    or receipt['offline_passed'] is not True
                    or receipt['native_executed'] is not False):
                raise ValueError('Offline candidate proof differs')
            if (cfg['case_id'] != entry['case_id']
                    or cfg['selected_case_id'] != entry['case_id']
                    or cfg['candidate_id'] != ident
                    or cfg['spawn_point_index'] != ['primary', 'fallback1',
                                                   'fallback2', 'fallback3'].index(ident)
                    or cfg['duration_s'] != 30 or cfg['rate_hz'] != 20
                    or [x['name'] for x in cfg['cameras']] != VIEWS):
                raise ValueError('Exact capture config differs')
            configs[case, ident] = cfg
    for case in ('reference', 'contrast'):
        primary = configs[case, 'primary']
        for ident in ('fallback1', 'fallback2', 'fallback3'):
            fallback = configs[case, ident]
            changed = {k for k in primary if primary[k] != fallback[k]}
            if changed != {'candidate_id', 'spawn_point_index'}:
                raise ValueError('Fallback changed comparison context')
    reference = configs['reference', 'primary']
    contrast = configs['contrast', 'primary']
    differences = {k for k in reference if reference[k] != contrast[k]}
    if differences != {'case_id', 'selected_case_id', 'case', 'control_phases'}:
        raise ValueError('Comparison confounded by another setting')
    if ([x['throttle'] for x in reference['control_phases']]
            != [0.28, 0.75, 0.92, 0.20]
            or [x['throttle'] for x in contrast['control_phases']]
            != [0.28, 0.28, 0.28, 0.20]):
        raise ValueError('Control contrast differs')
    output = {'format': 'c229597-draft-comparison-audit',
              'manifest_sha256': sha(P / 'draft-primary-manifest.json'),
              'offline_index_sha256': sha(P / 'draft-offline-index.json'),
              'candidates_checked': 8,
              'only_comparison_control_changed': True,
              'only_fallback_spawn_changed': True,
              'native_observed': False, 'selected': False,
              'legal_exhibition_claimed': False, 'delivery_ready': False}
    (P / 'draft-matrix-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'candidates_checked': 8, 'passed': True}))


if __name__ == '__main__':
    main()
