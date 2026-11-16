"""Construct and offline-check exact 86/97 m 300 ft context probes."""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT / 'cases/signal_advance_100_at'
OLD = 'signal_advance_100_at'
PROBES = {'signal_advance_300_below_86': 86.0,
          'signal_advance_300_above_97': 97.0}
INDEX = ROOT / 'signal-300-sides-draft-index.json'
MANIFEST = ROOT / 'signal-300-sides-draft-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def once(content, old, new):
    if content.count(old) != 1:
        raise ValueError('Source construction changed: ' + old)
    return content.replace(old, new)


def build():
    selected_manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    selected = next(row for row in selected_manifest['cases']
                    if row['case_id'].endswith('__' + OLD))
    cases, runtime_cases = [], []
    for suffix, distance in PROBES.items():
        variants = []
        folder = ROOT / 'cases' / suffix
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            filename = 'construction.json' if candidate == 'primary' else candidate + '-construction.json'
            construction = copy.deepcopy(json.loads((SOURCE / filename).read_text()))
            construction['case_id'] = ROOT.name + '__' + suffix
            for item in construction['files']:
                content = item['content'].replace(OLD, suffix)
                if item['path'] == 'config.json':
                    config = json.loads(content)
                    config['signal_target_m'] = distance
                    content = json.dumps(config, indent=2) + '\n'
                elif item['path'] == 'runner.py':
                    content = once(content, "config.get('signal_target_m') != 30.48",
                                   f"config.get('signal_target_m') != {distance:.1f}")
                    content = once(content, 'Exact 30.48 m signal probe required',
                                   f'Exact {distance:.1f} m signal probe required')
                elif item['path'] == 'finalizer.py':
                    content = once(content, 'probes_m=(30.48,)', 'probes_m=(91.44,)')
                    content = content.replace("['probes']['30.48']", "['probes']['91.44']")
                    content = once(content, 'continuous_left_signal_at_least_30_48_m',
                                   'continuous_left_signal_at_least_91_44_m')
                    if distance < 91.44:
                        content = once(content,
                                       "{'target':'continuous_left_signal_at_least_91_44_m',\n                        'requested':True,",
                                       "{'target':'continuous_left_signal_at_least_91_44_m',\n                        'requested':False,")
                        expression = "signal_advance['probes']['91.44']['observable_distance_met'] and signal_advance['probes']['91.44']['full_signal_onset_observed']"
                        content = once(content, "'matched':" + expression,
                                       "'matched':not (" + expression + ")")
                item['content'] = content
            path = folder / filename
            write(path, construction)
            variants.append({'id': candidate, 'construction': str(path.relative_to(ROOT)),
                             'construction_sha256': sha(path)})
        case_id = ROOT.name + '__' + suffix
        cases.append({'case_id': case_id, 'kind': 'diagnostic_unselected',
                      'signal_target_m': distance, 'reference_m': 91.44,
                      'district_classification': 'unresolved',
                      'legal_or_native_acceptance_claimed': False,
                      'variants': variants})
        entry = copy.deepcopy(selected)
        for key in ('offline', 'compatibility', 'post_capture', 'delivery_acceptance',
                    'physical_preparation', 'negative', 'fixture_recipe'):
            entry.pop(key, None)
        entry.update(case_id=case_id, kind='diagnostic_unselected',
                     construction=variants[0]['construction'],
                     construction_sha256=variants[0]['construction_sha256'],
                     signal_target_m=distance)
        for candidate, variant in zip(entry['candidates'], variants[1:]):
            for key in ('offline', 'compatibility', 'post_capture'):
                candidate.pop(key, None)
            candidate['construction'] = variant['construction']
            candidate['construction_sha256'] = variant['construction_sha256']
        runtime_cases.append(entry)
    write(INDEX, {'format': 'worker-signal-300-sides-construction-draft',
                  'assignment_id': ROOT.name, 'source_case': selected['case_id'],
                  'cases': cases})
    write(MANIFEST, {'format': selected_manifest['format'],
                     'assignment_id': ROOT.name,
                     'runtime_manifest_sha256': selected_manifest['runtime_manifest_sha256'],
                     'cases': runtime_cases})
    return cases


def prove(cases, tag):
    from signal_advance_audit import measure
    manifest = json.loads(MANIFEST.read_text())
    if len(cases) != 2 or len(manifest['cases']) != 2:
        raise ValueError('Two exact companion cases required')
    evidence = []
    for case, runtime_case in zip(cases, manifest['cases']):
        distance = case['signal_target_m']
        steps = 400
        rows = [{'frame': i, 'time_s': (i + 1) / 20,
                 'ego': {'position_xy_m': [i * distance / steps, 0.0]},
                 'ego_heading_deg': 20.0 if i == steps + 2 else 0.0,
                 'ego_left_indicator': i >= 1} for i in range(steps + 3)]
        observed = measure(rows, probes_m=(91.44,))
        if (abs(observed['observed_continuous_approach_distance_m'] - distance) > 1e-8
                or observed['probes']['91.44']['observable_distance_met'] != (distance >= 91.44)
                or not observed['probes']['91.44']['full_signal_onset_observed']
                or observed['legal_verdict_asserted']):
            raise ValueError('Original-shaped companion boundary measurement differs')
        if case['case_id'] != runtime_case['case_id'] or len(case['variants']) != 4:
            raise ValueError('Case identity or variant count differs')
        for variant in case['variants']:
            path = ROOT / variant['construction']
            if sha(path) != variant['construction_sha256']:
                raise ValueError('Construction hash changed')
            construction = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            config = json.loads(files['config.json'])
            expected = distance >= 91.44
            if (construction['case_id'] != case['case_id']
                    or config['selected_case_id'] != case['case_id']
                    or config['signal_target_m'] != distance or config['rate_hz'] != 20
                    or config['duration_s'] != 45 or len(config['cameras']) != 4
                    or f"config.get('signal_target_m') != {distance:.1f}" not in files['runner.py']
                    or ("'requested':" + str(expected) + ',') not in files['finalizer.py']):
                raise ValueError('Exact companion construction differs')
            output = f'.runtime-work/c109749-signal-300-{int(distance)}-{variant["id"]}-offline-{tag}'
            command = [str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                       '--manifest', str(MANIFEST.relative_to(REPO)),
                       '--case', case['case_id'], '--output', output]
            if variant['id'] != 'primary':
                command.extend(['--candidate', variant['id']])
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            if process.returncode:
                raise ValueError('Exact offline failed: ' + ' '.join(command) + '\n'
                                 + process.stdout + process.stderr)
            receipt = json.loads(process.stdout)
            log = Path(receipt['log'])
            if (receipt['case_id'] != case['case_id']
                    or receipt['candidate_id'] != variant['id']
                    or receipt['offline_passed'] is not True
                    or receipt['simulation_started'] is not False or not log.is_file()
                    or 'OK' not in log.read_text()):
                raise ValueError('Offline receipt or tests differ')
            evidence.append({'case_id': case['case_id'], 'candidate_id': variant['id'],
                             'observed_m': observed['observed_continuous_approach_distance_m'],
                             'construction_sha256': sha(path),
                             'offline_log_sha256': sha(log),
                             'command': ' '.join(command)})
    return {'format': 'worker-signal-300-sides-offline-proof',
            'manifest_sha256': sha(MANIFEST), 'paths': evidence,
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prove-only', action='store_true')
    parser.add_argument('--tag', default='v1')
    args = parser.parse_args()
    cases = json.loads(INDEX.read_text())['cases'] if args.prove_only else build()
    print(json.dumps(prove(cases, args.tag), indent=2))
