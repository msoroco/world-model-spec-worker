"""Bind current exact CPU receipts into the 13-case delivery draft.

Missing proof fields stay absent until their CPU chains finish; this builder
never promotes result.json or asserts Native/physical/legal acceptance.
"""
import copy
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / '.runtime-work/c179480-native-sweep'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def copied(source, name):
    target = HERE / name
    if not source.is_file():
        raise ValueError('Required current proof file missing: ' + str(source))
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return target.name, sha(target)


def proof(entry, candidate, kind, asset_tag, audit_rows):
    cid = entry['case_id']
    selected = entry if candidate == 'primary' else next(
        item for item in entry['candidates'] if item['id'] == candidate)
    log_tag = 'base-current' if kind == 'base' else 'sweep-qualified-v3'
    offline_log = HERE / f'{log_tag}-{cid}-{candidate}-offline.log'
    if not offline_log.is_file() or not read(offline_log)['offline_passed']:
        raise ValueError('Exact current offline proof missing: ' + cid + '/' + candidate)
    selected['offline'] = {
        'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
        'command': (f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/'
                    f'{"candidate-matrix-manifest.json" if kind == "base" else "sweep-candidate-manifest.json"}'
                    f' --case {cid} --candidate {candidate} --output '
                    f'.runtime-work/c179480-native-sweep/offline-{asset_tag}/{cid}/{candidate}'),
        'log': offline_log.name, 'log_sha256': sha(offline_log)}
    if kind == 'base':
        row = audit_rows[cid, candidate]
        selected['compatibility'] = {
            'receipt': row['artifacts']['compatibility']['path'],
            'sha256': row['artifacts']['compatibility']['sha256'],
            'log': row['artifacts']['analysis_log']['path'],
            'negative_log': row['artifacts']['negative_log']['path']}
        selected['saved_processing'] = {
            'receipt': row['artifacts']['processing']['path'],
            'sha256': row['artifacts']['processing']['sha256']}
        return row['artifacts']['negative_log']['path']
    attempt = ASSETS / 'compatibility-qualified-v3' / cid / candidate
    log = HERE / f'sweep-qualified-v3-{cid}-{candidate}-compatibility.log'
    if not log.is_file():
        return None
    receipt = read(log)
    if (not receipt['passed'] or receipt['case_id'] != cid or
            receipt['candidate_id'] != candidate or
            receipt['construction_sha256'] != selected['construction_sha256']):
        return None
    stem = f'selected-sweep-{cid}-{candidate}'
    receipt_name, receipt_hash = copied(attempt / 'compatibility.json', stem + '-compatibility.json')
    analysis_name, _ = copied(attempt / 'compatibility-analysis.log', stem + '-analysis.log')
    negative_name, _ = copied(attempt / 'negative-analysis.log', stem + '-negative.log')
    selected['compatibility'] = {'receipt': receipt_name, 'sha256': receipt_hash,
                                 'log': analysis_name, 'negative_log': negative_name}
    saved_log = HERE / f'sweep-qualified-v3-{cid}-{candidate}-saved.log'
    if saved_log.is_file():
        saved_result = read(saved_log)
        if (saved_result['passed'] and saved_result['recorded_only'] and
                saved_result['case_id'] == cid and
                saved_result['candidate_id'] == candidate and
                saved_result['originals_preserved']):
            receipt_path = ASSETS / 'saved-qualified-v3' / cid / candidate / 'v0001/processing.json'
            saved_name, saved_hash = copied(receipt_path, stem + '-saved.json')
            selected['saved_processing'] = {'receipt': saved_name, 'sha256': saved_hash,
                                            'command_log': saved_log.name,
                                            'command_log_sha256': sha(saved_log)}
    return negative_name


def build():
    base = read(HERE / 'candidate-matrix-manifest.json')
    sweep = read(HERE / 'sweep-candidate-manifest.json')
    if base['runtime_manifest_sha256'] != sweep['runtime_manifest_sha256']:
        raise ValueError('Base and sweep bind different current runtimes')
    audit_rows = {(row['case_id'], row['candidate_id']): row for row in
                  read(HERE / 'base-current-candidate-matrix-audit.json')['rows']}
    physical_base = {row['case_id']: row for row in
                     read(HERE / 'update160-physical-receipts-index.json')['receipts']}
    physical_sweep = {row['case_id']: row for row in
                      read(HERE / 'sweep-qualified-physical-index.json')['receipts']}
    entries = []
    missing = []
    for kind, source, physical, tag in (
            ('base', base, physical_base, 'base-current'),
            ('sweep', sweep, physical_sweep, 'qualified-v3')):
        for original in source['cases']:
            entry = copy.deepcopy(original)
            cid = entry['case_id']
            entry['kind'] = 'delivery'
            entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                       'host_env_var': 'CARLA_HOST',
                                       'port_env_var': 'CARLA_PORT'}
            item = physical[cid]
            entry['physical_preparation'] = {'receipt': item['receipt'],
                                              'sha256': item['sha256']}
            construction = read(HERE / entry['construction'])
            config = json.loads(next(file['content'] for file in construction['files']
                                     if file['path'] == 'config.json'))
            names = set(config.get('required_atoms', [])) | {
                channel['name'] for channel in construction['recording_description']['channels']}
            entry['acquisition'] = {name: {'entrypoint': 'native_finalize.py',
                'method': 'derive from retained original actor, frame, map and four-camera sources',
                'evidence': 'native-actors.jsonl; video_frames.jsonl; native-map-readback.json; four named source videos'}
                for name in sorted(names)}
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                negative = proof(entry, candidate, kind, tag, audit_rows)
                if candidate == 'primary':
                    if negative:
                        entry['negative'] = {'log': negative}
                    else:
                        missing.append(cid + '/primary compatibility')
                elif not negative:
                    missing.append(cid + '/' + candidate + ' compatibility')
            entries.append(entry)
    if len(entries) != 13:
        raise ValueError('All 13 nonbaseline cases required')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': base['runtime_manifest_sha256'],
                'status': 'draft_cpu_preparation_incomplete', 'cases': entries,
                'remaining_cpu_proofs': missing,
                'native_or_legal_acceptance_claimed': False}
    target = HERE / 'execution-manifest.json'
    write(target, manifest)
    return {'manifest': target.name, 'sha256': sha(target),
            'case_count': len(entries), 'missing_compatibility': len(missing)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2, sort_keys=True))
