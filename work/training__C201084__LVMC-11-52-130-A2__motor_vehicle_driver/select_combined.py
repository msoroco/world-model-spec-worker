"""Select the eight authored cases and retain traceable CPU receipt bindings."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DRAFT = HERE / 'current-combined-delivery-draft.json'
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spec(group, candidate, construction_sha):
    base = 'current-combined-' + group + '-' + candidate
    suffix = '-v2' if group == 'reference' and candidate == 'primary' else ''
    receipt_path = HERE / (base + '-compatibility' + suffix + '.log')
    receipt = json.loads(receipt_path.read_text())
    attempt = ROOT / '.runtime-work' / ('c201084-combined-' + group + '-' +
                                         candidate + '-compatibility' + suffix)
    source_log = attempt / 'compatibility-analysis.log'
    returned_log = HERE / 'selected-compatibility-analysis' / (group + '-' + candidate + '.log')
    returned_log.parent.mkdir(parents=True, exist_ok=True)
    if sha(source_log) != receipt['log_sha256'] or receipt['construction_sha256'] != construction_sha:
        raise ValueError('Current compatibility receipt differs: ' + base)
    shutil.copyfile(source_log, returned_log)
    negative = HERE / (base + '-negative-analysis.log')
    if sha(negative) != receipt['negative_log_sha256']:
        raise ValueError('Required-source negative differs: ' + base)
    offline_log = HERE / (base + '-offline.log')
    selection = json.loads((HERE / (base + '-offline-selection.json')).read_text())
    if selection['construction_sha256'] != construction_sha or \
            selection['manifest_sha256'] != sha(DRAFT):
        raise ValueError('Combined offline selection differs: ' + base)
    offline = {'command': '.venv-cpu/bin/python runtime.py offline --manifest ' +
               str(DRAFT.relative_to(ROOT)) + ' --case ' + selection['case_id'] +
               ' --candidate ' + candidate + ' --output .runtime-work/c201084-combined-' +
               group + '-' + candidate + '-offline',
               'exit_code': 0, 'construction_sha256': construction_sha,
               'log': str(offline_log.relative_to(HERE)), 'log_sha256': sha(offline_log)}
    compatibility = {'receipt': str(receipt_path.relative_to(HERE)),
                     'sha256': sha(receipt_path),
                     'log': str(returned_log.relative_to(HERE)),
                     'negative_log': str(negative.relative_to(HERE))}
    return offline, compatibility


def build():
    draft = json.loads(DRAFT.read_text())
    physical = json.loads((HERE / 'physical-proof/index.json').read_text())
    if physical['combined_manifest_sha256'] != sha(DRAFT):
        raise ValueError('Physical proof binds another combined draft')
    physical_by_case = {row['case_id']: row for row in physical['cases']}
    if len(physical_by_case) != len(GROUPS):
        raise ValueError('Missing physical preparation case')
    entries = []
    for group in GROUPS:
        entry = next(item for item in draft['cases'] if item['case_id'].endswith('__' + group))
        selected = dict(entry)
        selected['physical_preparation'] = physical_by_case[entry['case_id']]
        selected['offline'], selected['compatibility'] = spec(group, 'primary', entry['construction_sha256'])
        selected['negative'] = {'log': selected['compatibility']['negative_log']}
        saved_path = HERE / ('current-combined-' + group + '-primary-saved.log')
        saved = json.loads(saved_path.read_text())
        if saved['case_id'] != entry['case_id'] or saved['candidate_id'] != 'primary' or \
                saved['passed'] is not True or saved['recorded_only'] is not True:
            raise ValueError('Combined primary saved receipt differs: ' + group)
        selected['saved_processing'] = {'receipt': str(saved_path.relative_to(HERE)),
                                        'sha256': sha(saved_path)}
        construction = json.loads((HERE / entry['construction']).read_text())
        channels = [item['name'] for item in construction['recording_description']['channels']]
        files = {item['path'] for item in construction['files']}
        acquisition = {}
        for channel in channels:
            if channel == 'lead_traffic_relation':
                source = 'exception_measurement.py'
            elif channel == 'lead_traffic_presence':
                source = 'traffic_pair_measurement.py'
            else:
                source = 'source_measurement.py'
            if source not in files:
                raise ValueError('Missing acquisition implementation: ' + group + '/' + channel)
            acquisition[channel] = {'entrypoint': source,
                                    'method': 'derive ' + channel + ' from retained actor and frame sources',
                                    'evidence': 'native-actors.jsonl, video_frames.jsonl, native-survey-readback.json'}
        selected['acquisition'] = acquisition
        selected['candidates'] = []
        for candidate in entry['candidates']:
            bound = dict(candidate)
            bound['offline'], bound['compatibility'] = spec(group, candidate['id'],
                                                            candidate['construction_sha256'])
            selected['candidates'].append(bound)
        selected['preparation_status'] = 'selected_requires_exact_manifest_cpu_reproof'
        entries.append(selected)
    selected_manifest = {'format': 'worker-execution-manifest',
                         'assignment_id': HERE.name,
                         'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                         'status': 'selected_cpu_reproof_incomplete',
                         'delivery_ready': False, 'original_native_observed': False,
                         'source_draft_sha256': sha(DRAFT), 'cases': entries}
    destination = HERE / 'execution-manifest.json'
    destination.write_text(json.dumps(selected_manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'selected_cases': len(entries), 'fallbacks': sum(len(e['candidates']) for e in entries),
                      'manifest_sha256': sha(destination), 'exact_manifest_reproof_required': True}))


if __name__ == '__main__':
    build()
