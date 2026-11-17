"""Run and verify all armored visual-proxy saved CPU diagnostics."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = sys.executable
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(slug, candidate, attempt, output):
    version = output / 'v0001'
    processing = json.loads((version / 'processing.json').read_text())
    result = json.loads((version / 'analysis/result.json').read_text())
    observation = result['measured_values']['signed_curb_observation']
    config = json.loads((attempt / 'config.json').read_text())
    manifest = json.loads((ROOT / ('execution-manifest-diagnostic-' + slug +
                                    '-draft.json')).read_text())
    entry = manifest['cases'][0]
    declared = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    sign = '_signed_' in slug
    business = slug.endswith('_business') and not slug.endswith('_no_business')
    construction = ROOT / declared['construction']
    if declared['construction_sha256'] != sha(construction) or \
       json.loads(construction.read_text()) != json.loads((attempt / 'construction.json').read_text()) or \
       processing['case_id'] != ROOT.name + '__' + slug or \
       processing['candidate_id'] != candidate or \
       processing['passed'] is not True or \
       processing['timestamp_joins']['frames'] != 361 or \
       processing['timestamp_joins']['passed'] is not True or \
       processing['final_video_checks']['frames'] != 361 or \
       processing['final_video_checks']['passed'] is not True or \
       processing['physical_acceptance_claimed'] or \
       processing['legal_acceptance_claimed'] or \
       processing['missing_evidence'] or \
       observation['source_kind'] != 'synthetic_native_sample' or \
       observation['frames'] != 361 or \
       observation['red_curb_stationary_duration_s'] != 12 or \
       observation['sign_present'] != sign or \
       observation['native_blueprint'] != config['native_blueprint'] or \
       [e['name'] for e in observation['recorded_activity_events']] != (
           ['business_activity'] if business else []) or \
       observation['necessary_business_established'] is not None:
        raise ValueError('Terminal armored saved proof differs: ' + slug + '/' + candidate)
    source_decodes = []
    hashes = {sha(attempt / (view + '.mkv')) for view in VIEWS}
    for index in range(4):
        receipt = json.loads((version / f'source-{index}.json').read_text())
        if receipt['frames'] != 361 or receipt['passed'] is not True or \
           receipt['video_sha256'] not in hashes:
            raise ValueError('Armored four-camera source decode differs')
        source_decodes.append(receipt['video_sha256'])
    if len(set(source_decodes)) != 4:
        raise ValueError('Distinct armored source views missing')
    return {'case': slug, 'candidate': candidate,
            'construction_sha256': sha(attempt / 'construction.json'),
            'processing_sha256': sha(version / 'processing.json'),
            'four_source_decodes': True, 'frames': 361,
            'visual_proxy_only': True, 'native_executed': False,
            'legal_armored_identity_verified': False}


def main():
    records = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            slug = 'armored_car_' + sign + '_' + activity
            prefix = 'c150142-armored-' + sign + '-' + activity + '-'
            manifest = ROOT / ('execution-manifest-diagnostic-' + slug + '-draft.json')
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                attempt = REPO / '.runtime-work' / (prefix + candidate + '-native-v1')
                special = sign == 'unsigned' and activity == 'business' and candidate == 'primary'
                output = REPO / '.runtime-work' / (prefix + candidate +
                                                  ('-result-v2' if special else '-result-v1'))
                if not special:
                    prep = subprocess.run([PYTHON, str(ROOT / 'prepare-armored-saved.py'),
                        '--slug', slug, '--candidate', candidate, '--attempt', str(attempt)],
                        cwd=REPO, capture_output=True, text=True, timeout=300)
                    if prep.returncode:
                        raise RuntimeError('Armored prep failed: ' + slug + '/' + candidate +
                                           '\n' + prep.stderr[-2000:])
                    command = [PYTHON, str(REPO / 'runtime.py'), 'process-saved',
                        '--manifest', str(manifest), '--case', ROOT.name + '__' + slug,
                        '--attempt', str(attempt), '--output', str(output),
                        '--library', str(REPO / 'runtime/pipeline/library'),
                        '--validator', str(REPO /
                            '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]
                    log = REPO / '.runtime-work' / (prefix + candidate + '-process-v1.log')
                    with log.open('x') as stream:
                        process = subprocess.run(command, cwd=REPO, stdout=stream,
                            stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONHASHSEED='0'),
                            timeout=300)
                    if process.returncode:
                        raise RuntimeError('Armored saved processing failed: ' +
                                           slug + '/' + candidate + '\n' +
                                           log.read_text()[-2000:])
                records.append(verify(slug, candidate, attempt, output))
                print(slug, candidate, 'saved-pass', flush=True)
    target = ROOT / 'update043-armored-saved-matrix.json'
    target.write_text(json.dumps({'kind': 'armored_visual_proxy_saved_diagnostic',
                                  'count': len(records), 'records': records},
                                 indent=2, allow_nan=False) + '\n')
    print(json.dumps({'count': len(records), 'all_passed': True,
                      'receipt': str(target.relative_to(REPO))}))


if __name__ == '__main__':
    main()
