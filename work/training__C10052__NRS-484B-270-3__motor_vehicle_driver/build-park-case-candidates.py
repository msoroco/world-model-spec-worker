"""Build distinct unselected held/released park cases from the exact stop source family."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SUFFIXES = ('probe_park_released', 'probe_park_held')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def replace_once(source, old, new, label):
    if source.count(old) != 1:
        raise ValueError('Exact park source patch target differs: ' + label)
    return source.replace(old, new)


def park_files(source, suffix, candidate):
    files = []
    for file in source['files']:
        name, content = file['path'], file['content']
        if name == 'geometry.py':
            content = replace_once(content,
                "STOP_Y_M = {'probe_a': -1.5, 'probe_b': -4.0}",
                "STOP_Y_M = {'probe_a': -1.5, 'probe_b': -4.0, "
                "'probe_park_released': -4.0, 'probe_park_held': -4.0}", name)
        elif name == 'runner.py':
            content = replace_once(content,
                "hand_brake=command['hand_brake']))",
                "hand_brake=(command['hand_brake'] and suffix == 'probe_park_held')))", name)
        elif name == 'finalize.py':
            content = replace_once(content,
                "requested = {'probe_a': 0.0, 'probe_b': 9.36}[config['case_suffix']]",
                "requested = {'probe_a': 0.0, 'probe_b': 9.36, "
                "'probe_park_released': 9.36, 'probe_park_held': 9.36}[config['case_suffix']]", name)
            needle = '    from worker_exchange.native_output import validate_result\n'
            addition = (
                "    expected_park = config['case_suffix'] == 'probe_park_held'\n"
                "    if 'parking_control_observation' not in measurements:\n"
                "        raise ValueError('Missing required source: park-act-sources.json')\n"
                "    observed_park = measurements['parking_control_observation']['value']['park_control_candidate']\n"
                "    result['target_checks'].append({'target': 'sustained applied hand brake during stopped facility occupancy',\n"
                "        'requested': expected_park, 'measured': observed_park,\n"
                "        'method': 'source-hashed original Native control and full-body pose join',\n"
                "        'tolerance': 'at least 40 contiguous 20 Hz frames',\n"
                "        'matched': observed_park == expected_park, 'physical_cause_confirmed': False,\n"
                "        'cause_evidence': ['native_controls.jsonl', 'native_samples.jsonl',\n"
                "                           'park-act-sources.json']})\n"
            )
            content = replace_once(content, needle, addition + needle, name)
        elif name == 'fallback_triggers.py':
            content = replace_once(content,
                "if suffix not in ('probe_a', 'probe_b'):",
                "if suffix not in ('probe_a', 'probe_b', 'probe_park_released', 'probe_park_held'):", name)
        elif name == 'config.json':
            config = json.loads(content)
            case_id = AID + '__' + suffix
            config.update(case_id=case_id, case_suffix=suffix, candidate_id=candidate,
                          selected_case_id=case_id, supported_case_ids=[case_id],
                          case={'case_id': case_id})
            content = json.dumps(config, indent=2) + '\n'
        files.append({'path': name, 'content': content})
    return files


def main():
    original = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    base = next(c for c in original['cases'] if c['case_id'].endswith('__probe_b'))
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases = {c['case_id'] for c in plan['cases']}
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID,
                'runtime_manifest_sha256': original['runtime_manifest_sha256'],
                'status': 'draft_not_selected', 'cases': []}
    for suffix in SUFFIXES:
        case_id = AID + '__' + suffix
        if case_id not in cases:
            raise ValueError('Park case missing from case plan: ' + suffix)
        contract = json.loads((HERE / 'draft-park-control-measurement-contract.json').read_text())
        contract['case_id'] = case_id
        contract['controlled_contrast']['target_held_control'] = suffix == 'probe_park_held'
        contract['unresolved'] = [gap for gap in contract['unresolved']
                                  if not gap.startswith('separate park case IDs')]
        contract_path = HERE / 'draft-park-cases' / suffix / 'measurement-contract.json'
        write(contract_path, contract)
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'candidate_risk': {'status': 'physical',
                    'reason': 'Original Native stop, applied control, facility designation and statutory exceptions need saved review'},
                 'measurement_contract': contract_path.relative_to(HERE).as_posix(),
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                    'output_schema': 'c10052-full-saved-occupancy-diagnostic-v1'},
                 'candidates': []}
        for name in NAMES:
            ref = base if name == 'primary' else next(x for x in base['candidates'] if x['id'] == name)
            source = json.loads((HERE / ref['construction']).read_text())
            candidate = dict(source)
            candidate['case_id'] = case_id
            candidate['files'] = park_files(source, suffix, name)
            candidate['measurement_plan'] = {'method': 'original Native applied hand brake and stopped full-body facility overlap',
                                             'status': 'unselected_cpu_diagnostic_pending_original_review'}
            candidate['static_checks'] = source['static_checks'] + [
                'held/released command policy differs while route and stop geometry stay fixed']
            candidate['status'] = 'unselected_cpu_draft'
            path = HERE / 'draft-park-cases' / suffix / name / 'construction.json'
            write(path, candidate)
            row = {'id': name, 'construction': path.relative_to(HERE).as_posix(),
                   'construction_sha256': sha(path)}
            if name == 'primary':
                entry.update(row)
            else:
                row.update(trigger=ref['trigger'], changed_knobs=ref['changed_knobs'])
                entry['candidates'].append(row)
        manifest['cases'].append(entry)
    path = HERE / 'draft-park-execution-manifest.json'
    write(path, manifest)
    return {'cases': 2, 'candidates': 8, 'manifest_sha256': sha(path),
            'status': 'draft_not_selected'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
