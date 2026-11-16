"""Construct and offline-check the exact 91.44 m signal-context draft.

The 300 ft rule is conditional on context. This is an authored CPU probe,
without a district classification or legal/physical sufficiency finding.
"""
import copy
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'cases/signal_advance_100_at'
SUFFIX = 'signal_advance_300_at'
OLD = 'signal_advance_100_at'
CASE_ID = ROOT.name + '__' + SUFFIX
INDEX = ROOT / 'signal-300-at-draft-index.json'
MANIFEST = ROOT / 'signal-300-at-draft-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def change_once(content, old, new):
    if content.count(old) != 1:
        raise ValueError('Source signal construction changed: ' + old)
    return content.replace(old, new)


def build():
    selected_manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    selected = next(row for row in selected_manifest['cases']
                    if row['case_id'].endswith('__' + OLD))
    variants = []
    folder = ROOT / 'cases' / SUFFIX
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        filename = 'construction.json' if candidate == 'primary' else candidate + '-construction.json'
        construction = copy.deepcopy(json.loads((SOURCE / filename).read_text()))
        construction['case_id'] = CASE_ID
        for item in construction['files']:
            content = item['content'].replace(OLD, SUFFIX)
            if item['path'] == 'config.json':
                config = json.loads(content)
                config['signal_target_m'] = 91.44
                content = json.dumps(config, indent=2) + '\n'
            elif item['path'] == 'runner.py':
                content = change_once(content, "config.get('signal_target_m') != 30.48",
                                      "config.get('signal_target_m') != 91.44")
                content = change_once(content, 'Exact 30.48 m signal probe required',
                                      'Exact 91.44 m signal probe required')
            elif item['path'] == 'finalizer.py':
                content = change_once(content, 'probes_m=(30.48,)', 'probes_m=(91.44,)')
                content = content.replace("['probes']['30.48']", "['probes']['91.44']")
                content = change_once(content, 'continuous_left_signal_at_least_30_48_m',
                                      'continuous_left_signal_at_least_91_44_m')
            item['content'] = content
        path = folder / filename
        write(path, construction)
        variants.append({'id': candidate, 'construction': str(path.relative_to(ROOT)),
                         'construction_sha256': sha(path)})
    entry = copy.deepcopy(selected)
    for key in ('offline', 'compatibility', 'post_capture', 'delivery_acceptance',
                'physical_preparation', 'negative', 'fixture_recipe'):
        entry.pop(key, None)
    entry.update(case_id=CASE_ID, kind='diagnostic_unselected',
                 construction=variants[0]['construction'],
                 construction_sha256=variants[0]['construction_sha256'],
                 signal_target_m=91.44)
    for candidate, variant in zip(entry['candidates'], variants[1:]):
        for key in ('offline', 'compatibility', 'post_capture'):
            candidate.pop(key, None)
        candidate['construction'] = variant['construction']
        candidate['construction_sha256'] = variant['construction_sha256']
    write(INDEX, {'format': 'worker-signal-300-at-construction-draft',
                  'assignment_id': ROOT.name, 'case_id': CASE_ID,
                  'source_case': selected['case_id'], 'target_m': 91.44,
                  'district_classification': 'unresolved',
                  'legal_or_native_acceptance_claimed': False,
                  'variants': variants})
    write(MANIFEST, {'format': selected_manifest['format'],
                     'assignment_id': ROOT.name,
                     'runtime_manifest_sha256': selected_manifest['runtime_manifest_sha256'],
                     'cases': [entry]})
    return variants


def prove(variants):
    from signal_advance_audit import measure
    # Independent exact-boundary measurement on original-shaped rows. The
    # full 900-frame sealed source fixture is separately retained.
    steps = 381
    step = 91.44 / steps
    rows = [{'frame': i, 'time_s': (i + 1) / 20,
             'ego': {'position_xy_m': [i * step, 0.0]},
             'ego_heading_deg': 20.0 if i == steps + 2 else 0.0,
             'ego_left_indicator': i >= 1} for i in range(steps + 3)]
    observed = measure(rows, probes_m=(91.44,))
    if (abs(observed['observed_continuous_approach_distance_m'] - 91.44) > 1e-8
            or not observed['probes']['91.44']['observable_distance_met']
            or not observed['probes']['91.44']['full_signal_onset_observed']
            or observed['legal_verdict_asserted']):
        raise ValueError('Exact original-shaped 91.44 m measurement failed')
    evidence = []
    for variant in variants:
        path = ROOT / variant['construction']
        if sha(path) != variant['construction_sha256']:
            raise ValueError('Construction hash changed')
        construction = json.loads(path.read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        if (construction['case_id'] != CASE_ID or config['selected_case_id'] != CASE_ID
                or config['signal_target_m'] != 91.44 or config['rate_hz'] != 20
                or config['duration_s'] != 45 or len(config['cameras']) != 4
                or "config.get('signal_target_m') != 91.44" not in files['runner.py']
                or "['probes']['91.44']" not in files['finalizer.py']):
            raise ValueError('Exact 91.44 m construction differs')
        output = '.runtime-work/c109749-signal-300-at-' + variant['id'] + '-offline-v3'
        command = [str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                   '--manifest', str(MANIFEST.relative_to(REPO)), '--case', CASE_ID,
                   '--output', output]
        if variant['id'] != 'primary':
            command.extend(['--candidate', variant['id']])
        process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        if process.returncode:
            raise ValueError('Exact offline failed: ' + ' '.join(command) + '\n'
                             + process.stdout + process.stderr)
        receipt = json.loads(process.stdout)
        log = Path(receipt['log'])
        if (receipt['case_id'] != CASE_ID or receipt['candidate_id'] != variant['id']
                or receipt['offline_passed'] is not True
                or receipt['simulation_started'] is not False or not log.is_file()
                or 'OK' not in log.read_text()):
            raise ValueError('Offline receipt or tests differ')
        evidence.append({'candidate_id': variant['id'],
                         'construction_sha256': sha(path),
                         'offline_log_sha256': sha(log),
                         'command': ' '.join(command)})
    return {'format': 'worker-signal-300-at-offline-proof', 'case_id': CASE_ID,
            'target_m': 91.44, 'observed_m': observed['observed_continuous_approach_distance_m'],
            'manifest_sha256': sha(MANIFEST), 'paths': evidence,
            'compatibility_or_saved_or_physical_acceptance_claimed': False,
            'legal_verdict_asserted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prove-only', action='store_true')
    args = parser.parse_args()
    variants = json.loads(INDEX.read_text())['variants'] if args.prove_only else build()
    print(json.dumps(prove(variants), indent=2))
