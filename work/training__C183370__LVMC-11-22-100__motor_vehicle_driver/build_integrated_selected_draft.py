"""Build one source-derived-channel draft from an exact selected C183370 candidate."""
import argparse
import hashlib
import json
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'
CHANNELS = ('ego_speed', 'newly_laid_footprint_contact',
            'drive_over_warned_new_pavement')


def _description(contract, module_name):
    namespace = {'__name__': module_name}
    old = sys.modules.get('recording_contract')
    if module_name == 'variant_recording_contract':
        stub = types.ModuleType('recording_contract')
        stub.ASSIGNMENT = HERE.name
        sys.modules['recording_contract'] = stub
    try:
        exec(compile(contract, module_name + '.py', 'exec'), namespace)
        return namespace['description'](600)
    finally:
        if module_name == 'variant_recording_contract':
            if old is None:
                del sys.modules['recording_contract']
            else:
                sys.modules['recording_contract'] = old


def build(short, candidate):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown candidate')
    manifest = json.loads(MANIFEST.read_text())
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == HERE.name + '__' + short), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    original = HERE / selected['construction']
    construction = json.loads(original.read_text())
    files = {item['path']: item for item in construction['files']}
    finalizer_path = entry['measurement_procedure']['entrypoint']
    if finalizer_path == 'native/finalize.py':
        contract_path = 'native/recording_contract.py'
    elif finalizer_path == 'native/variant_finalize.py':
        contract_path = 'native/variant_recording_contract.py'
    elif finalizer_path == 'native/newly_laid_finalize.py':
        contract_path = 'native/newly_laid_recording_contract.py'
    else:
        raise ValueError('Unexpected selected finalizer')
    module_name = Path(contract_path).stem
    contract = files[contract_path]['content']
    old_channels = "'pavement_footprint_contact')"
    new_channels = ("'pavement_footprint_contact',\n"
                    "            'ego_speed', 'newly_laid_footprint_contact',\n"
                    "            'drive_over_warned_new_pavement')")
    if contract.count(old_channels) != 1:
        raise ValueError('Recording contract shape changed')
    contract = contract.replace(old_channels, new_channels)
    files[contract_path]['content'] = contract
    files[contract_path].pop('source', None)

    finalizer = files[finalizer_path]['content']
    import_pattern = re.compile(r'^(from ' + re.escape(module_name) +
                                r' import CHANNELS[^\n]*)$', re.MULTILINE)
    finalizer, count = import_pattern.subn(
        r'\1\nfrom mandatory_channels import derive as derive_mandatory_channels',
        finalizer)
    if count != 1:
        raise ValueError('Finalizer contract import changed')
    finalizer, count = re.subn(r'(streams = \{name: .* for name in )CHANNELS(\})',
                               r'\1CHANNELS[:4]\2', finalizer)
    if count != 1:
        raise ValueError('Finalizer stream creation changed')
    context_line = next((line for line in finalizer.splitlines()
                         if line.strip().startswith('context = attempt')), None)
    if context_line is None or finalizer.count(context_line) != 1:
        raise ValueError('Finalizer context write changed')
    insertion = ("    mandatory_folder = attempt / 'mandatory-derived'\n"
                 "    derive_mandatory_channels(attempt, mandatory_folder)\n"
                 "    for name in CHANNELS[4:]:\n"
                 "        (mandatory_folder / (name + '.jsonl')).replace(folder / (name + '.jsonl'))\n")
    finalizer = finalizer.replace(context_line, insertion + context_line)
    if short.startswith('employee_exception_'):
        measurement_anchor = '''def measurement_records(analysis):
    return {'surveyed_pavement_contact': measure_variant_surveyed_pavement_contact(analysis),
            'control_actor_vicinity': measure_control_actor_vicinity(analysis)}
'''
        measurement_replacement = '''def measure_employee_activity_source(analysis, attempt):
    """Bind the chosen operator to retained activity references, without inferring status."""
    if analysis['control_kind'] != 'employee_exception':
        raise ValueError('Employee activity source requested for another control')
    readback = json.loads((Path(attempt) / 'live-readback.json').read_text())
    plan = readback['plan']
    route = analysis['case']
    if route not in ('employee_crossing', 'nonemployee_crossing'):
        raise ValueError('Unknown employee comparison route')
    sources = plan['source_references']
    employee = sources.get('employee_activity_source')
    nonemployee = sources.get('nonemployee_activity_source')
    selected = plan['cases'][route].get('operator_activity_source')
    expected = employee if route == 'employee_crossing' else nonemployee
    diagnostic = analysis.get('source_kind') == 'synthetic_diagnostic_capture'
    route_binding = (selected == 'synthetic_fixture_only_' + route + '_activity_unverified'
                     if diagnostic else selected == expected)
    if (not isinstance(employee, str) or not employee.strip() or
            not isinstance(nonemployee, str) or not nonemployee.strip() or
            employee == nonemployee or not route_binding):
        raise ValueError('Employee activity sources are not distinct and route-bound')
    actors = read_jsonl(Path(attempt) / 'native-actors.jsonl')
    actor_id = readback['control_actor_id']
    actor_type = readback['control_type_id']
    if not actors or any(row.get('control_actor_id') != actor_id or
                         row.get('control_type_id') != actor_type for row in actors):
        raise ValueError('Employee operator identity differs from retained actor rows')
    hashes = {name: analysis['source_hashes'][name] for name in MEASUREMENT_SOURCES}
    return {'method': 'measure_employee_activity_source',
            'value': {'operator_actor_id': actor_id,
                      'operator_type_id': actor_type,
                      'selected_route': route,
                      'activity_source_reference': selected,
                      'activity_source_route_bound': True,
                      'employment_verified': False,
                      'actually_engaged_in_paving_verified': False,
                      'legal_exception_applies': None},
            'sources': hashes}


def measurement_records(analysis, attempt):
    records = {'surveyed_pavement_contact': measure_variant_surveyed_pavement_contact(analysis),
               'control_actor_vicinity': measure_control_actor_vicinity(analysis)}
    if analysis['control_kind'] == 'employee_exception':
        records['employee_activity_source'] = measure_employee_activity_source(analysis, attempt)
    return records
'''
        if finalizer.count(measurement_anchor) != 1:
            raise ValueError('Employee finalizer measurement anchor changed')
        finalizer = finalizer.replace(measurement_anchor, measurement_replacement)
        if finalizer.count("'measurements': measurement_records(analysis),") != 1:
            raise ValueError('Employee measurement report anchor changed')
        finalizer = finalizer.replace("'measurements': measurement_records(analysis),",
                                      "'measurements': measurement_records(analysis, attempt),")
    files[finalizer_path]['content'] = finalizer
    files[finalizer_path].pop('source', None)
    source_module = HERE / 'derive_mandatory_channels.py'
    construction['files'].append({
        'path': 'native/mandatory_channels.py',
        'content': source_module.read_text(),
        'source': str(source_module.relative_to(HERE.parents[1])),
    })

    description = _description(contract, module_name)
    construction['recording_description'] = description
    config = json.loads(files['config.json']['content'])
    config['recording_description'] = description
    files['config.json']['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
    construction['status'] = 'partial'
    construction['delivery_ready'] = False
    target = HERE / 'draft-integrated-selected' / short / candidate / 'construction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')

    selected['construction'] = str(target.relative_to(HERE))
    selected['construction_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    selected['compatibility'] = None
    selected['offline'] = None
    entry['candidate_offline_status'] = 'pending'
    if candidate == 'primary':
        entry['post_capture'] = None
    draft_manifest = HERE / f'update153-integrated-{short}-{candidate}-manifest.json'
    draft_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return {'case': short, 'candidate': candidate,
            'construction_sha256': selected['construction_sha256'],
            'manifest': str(draft_manifest)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    print(json.dumps(build(args.case_suffix, args.candidate), sort_keys=True))
