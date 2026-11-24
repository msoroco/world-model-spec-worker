"""Resume current-runtime public compatibility for every short candidate."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'current-runtime-runner-offline-bound-manifest.json'
VALIDATOR = REPO / '.runtime-work/owner150142/current-decoder/.lake/build/bin/adapterCheck'
SCRATCH = REPO / '.runtime-work/owner150142/current-runner-short-public'
PORTABLE = ROOT / 'current-runtime-runner-public'
INDEX = ROOT / 'current-runtime-runner-short-public-index.json'
SHORTS = ('contrast', 'armored_car_signed_business',
          'armored_car_signed_no_business', 'armored_car_unsigned_business',
          'armored_car_unsigned_no_business',
          'emergency_vehicle_signed_business',
          'emergency_vehicle_signed_no_business',
          'emergency_vehicle_unsigned_business',
          'emergency_vehicle_unsigned_no_business', 'mail_adjacent_deposit',
          'mail_adjacent_no_deposit', 'mail_no_box_deposit',
          'ordinary_red_signed')
VARIANTS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_bytes(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=SCRATCH,
                                     prefix='portable-', delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, target)


def verify(case_id, candidate, field, output):
    proof = json.loads((output / 'compatibility.json').read_text(encoding='utf-8'))
    positive_log = output / 'positive-analysis.log'
    if not positive_log.is_file():
        positive_log = output / 'compatibility-analysis.log'
    if (proof.get('passed') is not True or proof.get('case_id') != case_id or
            proof.get('candidate_id') != candidate or
            proof.get('construction_sha256') != field['construction_sha256'] or
            not {'selected_measurements', 'negative_case_source', 'lean_decoder',
                 'final_decode'} <= set(proof.get('checks', []))):
        raise ValueError('Current public compatibility proof differs: ' + case_id + '/' + candidate)
    if (proof['log_sha256'] != sha(positive_log) or
            proof['negative_log_sha256'] != sha(output / 'negative-analysis.log') or
            proof['negative_error_contains'] not in (output / 'negative-analysis.log').read_text()):
        raise ValueError('Current public positive/negative log changed: ' + case_id + '/' + candidate)
    return proof


def one(item):
    case_id, candidate, field = item
    short = case_id.removeprefix(ROOT.name + '__')
    target = PORTABLE / short / candidate
    if (target / 'compatibility.json').is_file():
        proof = verify(case_id, candidate, field, target)
    else:
        scratch = SCRATCH / short / candidate
        if scratch.exists() and not (scratch / 'compatibility.json').is_file():
            raise ValueError('Incomplete scratch proof needs inspection: ' + str(scratch))
        if not scratch.exists():
            scratch.parent.mkdir(parents=True, exist_ok=True)
            log = SCRATCH / short / (candidate + '.command.log')
            command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                       '--manifest', str(SOURCE), '--case', case_id,
                       '--candidate', candidate, '--output', str(scratch),
                       '--library', str(REPO / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            env = os.environ.copy()
            env.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'runtime-output' / short / candidate))
            with log.open('w', encoding='utf-8') as stream:
                completed = subprocess.run(command, cwd=REPO, env=env,
                                           stdout=stream, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise ValueError('Current public compatibility failed: '
                                 + str(log.relative_to(REPO)))
        proof = verify(case_id, candidate, field, scratch)
        for name in ('compatibility.json', 'compatibility-analysis.log',
                     'negative-analysis.log'):
            portable_name = ('positive-analysis.log' if name ==
                             'compatibility-analysis.log' else name)
            destination = target / portable_name
            if destination.exists():
                if sha(destination) != sha(scratch / name):
                    raise ValueError('Portable public proof changed: ' + str(destination))
            else:
                atomic_bytes(destination, (scratch / name).read_bytes())
    return {'case_id': case_id, 'candidate_id': candidate,
            'construction_sha256': proof['construction_sha256'],
            'receipt': str((target / 'compatibility.json').relative_to(ROOT)),
            'receipt_sha256': sha(target / 'compatibility.json'),
            'log_sha256': proof['log_sha256'],
            'negative_log_sha256': proof['negative_log_sha256']}


def run(limit):
    if not VALIDATOR.is_file():
        raise ValueError('Pinned current Lean decoder missing')
    manifest = json.loads(SOURCE.read_text(encoding='utf-8'))
    cases = {entry['case_id']: entry for entry in manifest['cases']}
    jobs = []
    for short in SHORTS:
        case_id = ROOT.name + '__' + short
        entry = cases[case_id]
        fields = {'primary': entry, **{item['id']: item for item in entry['candidates']}}
        for variant in VARIANTS:
            jobs.append((case_id, variant, fields[variant]))
    if len(jobs) != 52:
        raise ValueError('Expected 13 short cases and 52 candidates')
    existing = {}
    if INDEX.is_file():
        prior = json.loads(INDEX.read_text(encoding='utf-8'))
        if prior['source_manifest_sha256'] != sha(SOURCE):
            raise ValueError('Current public progress index binds older manifest')
        existing = {(row['case_id'], row['candidate_id']): row for row in prior['rows']}
    pending = [item for item in jobs if (item[0], item[1]) not in existing]
    if limit is not None:
        pending = pending[:limit]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(one, item): item for item in pending}
        for future in as_completed(futures):
            row = future.result()
            existing[(row['case_id'], row['candidate_id'])] = row
            progress = {'format': 'c150142-current-runner-short-public-index-v1',
                        'source_manifest_sha256': sha(SOURCE),
                        'rows': sorted(existing.values(),
                                       key=lambda x: (x['case_id'], x['candidate_id'])),
                        'completed': len(existing), 'expected': len(jobs),
                        'original_native_observed': False,
                        'delivery_ready': False}
            atomic_bytes(INDEX, (json.dumps(progress, sort_keys=True, indent=2) + '\n').encode())
    return {'completed': len(existing), 'expected': len(jobs),
            'progress_index_sha256': sha(INDEX)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.limit), sort_keys=True))
