"""Build isolated exact signal-distance probes around the 30.48 m requirement."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'cases/signal_advance_100_at'
OLD = 'signal_advance_100_at'
PROBES = {'signal_advance_100_below_25': 25.0,
          'signal_advance_100_above_36': 36.0}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    cases = []
    selected_manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    selected = next(row for row in selected_manifest['cases']
                    if row['case_id'].endswith('__' + OLD))
    runtime_cases = []
    for suffix, distance in PROBES.items():
        folder = ROOT / 'cases' / suffix
        variants = []
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            filename = 'construction.json' if candidate == 'primary' else candidate + '-construction.json'
            base = json.loads((SOURCE / filename).read_text())
            case = copy.deepcopy(base)
            case['case_id'] = ROOT.name + '__' + suffix
            for item in case['files']:
                item['content'] = item['content'].replace(OLD, suffix)
                if item['path'] == 'config.json':
                    config = json.loads(item['content'])
                    config['signal_target_m'] = distance
                    item['content'] = json.dumps(config, indent=2) + '\n'
                elif item['path'] == 'runner.py':
                    old = "config.get('signal_target_m') != 30.48"
                    new = f"config.get('signal_target_m') != {distance:.1f}"
                    if item['content'].count(old) != 1:
                        raise ValueError('Source runner signal guard changed')
                    item['content'] = item['content'].replace(old, new)
                    item['content'] = item['content'].replace(
                        'Exact 30.48 m signal probe required',
                        f'Exact {distance:.1f} m signal probe required')
                elif item['path'] == 'finalizer.py' and distance < 30.48:
                    # The shortfall is an expected diagnostic observation, not
                    # a successful 30.48 m result or a legal finding.
                    anchor = "{'target':'continuous_left_signal_at_least_30_48_m',\n                        'requested':True,"
                    replacement = "{'target':'continuous_left_signal_at_least_30_48_m',\n                        'requested':False,"
                    expression = "signal_advance['probes']['30.48']['observable_distance_met'] and signal_advance['probes']['30.48']['full_signal_onset_observed']"
                    matched = "'matched':" + expression
                    if item['content'].count(anchor) != 1 or item['content'].count(matched) != 1:
                        raise ValueError('Source finalizer signal target changed')
                    item['content'] = item['content'].replace(anchor, replacement)
                    item['content'] = item['content'].replace(matched, "'matched':not (" + expression + ")")
            path = folder / filename
            write(path, case)
            variants.append({'id': candidate, 'construction': str(path.relative_to(ROOT)),
                             'construction_sha256': sha(path)})
        cases.append({'case_id': ROOT.name + '__' + suffix, 'kind': 'diagnostic_unselected',
                      'signal_target_m': distance, 'variants': variants,
                      'source_limit': 'Authored distance is an engineering input; Native signal-onset distance requires original-history review.'})
        runtime_entry = copy.deepcopy(selected)
        for key in ('offline', 'compatibility', 'post_capture', 'delivery_acceptance',
                    'physical_preparation', 'negative', 'fixture_recipe'):
            runtime_entry.pop(key, None)
        runtime_entry.update(case_id=ROOT.name + '__' + suffix,
                             kind='diagnostic_unselected',
                             construction=variants[0]['construction'],
                             construction_sha256=variants[0]['construction_sha256'],
                             signal_target_m=distance)
        for candidate, variant in zip(runtime_entry['candidates'], variants[1:]):
            for key in ('offline', 'compatibility', 'post_capture'):
                candidate.pop(key, None)
            candidate['construction'] = variant['construction']
            candidate['construction_sha256'] = variant['construction_sha256']
        runtime_cases.append(runtime_entry)
    manifest = {'format': 'worker-signal-distance-construction-draft',
                'assignment_id': ROOT.name, 'source_case': ROOT.name + '__' + OLD,
                'cases': cases}
    write(ROOT / 'signal-distance-draft-index.json', manifest)
    write(ROOT / 'signal-distance-draft-manifest.json', {
        'format': selected_manifest['format'],
        'assignment_id': ROOT.name,
        'runtime_manifest_sha256': selected_manifest['runtime_manifest_sha256'],
        'cases': runtime_cases})
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
