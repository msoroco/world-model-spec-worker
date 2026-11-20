"""Independent fixed-topology entry-order audit for the ending-road branch."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory

from ending_road_measurement import measure
from importlib.util import module_from_spec, spec_from_file_location


def measure_opposing_left(root):
    source = Path(root) / 'opposing_left_measurement.py'
    if not source.is_file():
        source = Path('.runtime-work/c295149-opposing-left-primary-saved-attempt-1/opposing_left_measurement.py')
    spec = spec_from_file_location('opposing_left_measurement', source)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure_opposing_left(root)


def audit(yield_case, proceed_case):
    left, right = Path(yield_case), Path(proceed_case)
    topology_name = 'intersection_topology.json'
    trace_name = 'intersection_participants.jsonl'
    for root in (left, right):
        for name in (topology_name, trace_name):
            if not (root / name).is_file():
                raise ValueError('Missing exact comparison original: ' + name)
    if sha256((left / topology_name).read_bytes()).digest() != sha256((right / topology_name).read_bytes()).digest():
        raise ValueError('Entry-order comparison changed fixed lane topology')
    first = []
    for root in (left, right):
        rows = [json.loads(line) for line in (root / trace_name).read_text().splitlines()]
        if not rows:
            raise ValueError('Entry-order comparison has no original frames')
        first.append(rows[0])
    for name in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if first[0].get(name) != first[1].get(name):
            raise ValueError('Entry-order comparison changed initial actor setup: ' + name)
    yielded = measure(left / topology_name, left / trace_name)
    proceeded = measure(right / topology_name, right / trace_name)
    if not yielded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Yield case does not contain a measured delayed entry')
    if proceeded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Proceed case did not change measured entry order')
    return {'passed': True, 'comparison_id': 'ending_through_yield_order',
            'yield_entry_delta_s': yielded['entry_delta_s'],
            'proceed_entry_delta_s': proceeded['entry_delta_s'],
            'legal_acceptance_claimed': False}


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _selected(manifest, suffix):
    here = Path(__file__).resolve().parent
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == here.name + '__' + suffix), None)
    if entry is None:
        raise ValueError('Missing selected exact comparison member: ' + suffix)
    tokens = shlex.split(entry['saved_processing_proof']['command'])
    attempt = Path(tokens[tokens.index('--attempt') + 1])
    receipt_path = here / entry['saved_processing_proof']['log']
    receipt = json.loads(receipt_path.read_text())
    if (not receipt.get('passed') or receipt.get('missing_evidence')
            or not receipt.get('recorded_only')
            or receipt.get('case_id') != entry['case_id']
            or receipt.get('candidate_id') != 'primary'
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']
            or _sha(receipt_path) != entry['saved_processing_proof']['log_sha256']):
        raise ValueError('Exact saved source receipt differs: ' + suffix)
    for name in ('intersection_topology.json', 'intersection_participants.jsonl',
                 'video_frames.jsonl', 'trace.jsonl') + tuple(
                     name for name in ('official_device_context.json',
                                       'official_geometry_binding.json',
                                       'official_device_states.jsonl')
                     if (attempt / name).is_file()):
        if _sha(attempt / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Original source hash differs: ' + suffix + '/' + name)
    if _sha(receipt['result']) != receipt['result_sha256']:
        raise ValueError('Saved measurement hash differs: ' + suffix)
    return attempt, {'case_id': entry['case_id'], 'saved_receipt_sha256': _sha(receipt_path),
                     'topology_sha256': _sha(attempt / 'intersection_topology.json'),
                     'participants_sha256': _sha(attempt / 'intersection_participants.jsonl')}


def audit_exact(comparison_id, *, tamper=False):
    """Audit exact retained originals; synthetic fixtures make no legal finding."""
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'execution-manifest.json').read_text())
    plan = json.loads((here / 'case-plan.json').read_text())
    spec = next((row for row in plan['comparisons']
                 if row['comparison_id'] == comparison_id), None)
    if comparison_id == 'opposing_left_exception' and spec is not None:
        return _audit_opposing_probe(manifest, spec, tamper=tamper)
    if spec is None or comparison_id not in ('ending_yield_order', 'arrival_window',
                                            'official_control'):
        raise ValueError('Unsupported exact source comparison: ' + comparison_id)
    suffixes = [case.rsplit('__', 1)[-1] for case in spec['case_ids']]
    (left, left_proof), (right, right_proof) = [_selected(manifest, s) for s in suffixes]
    topology = 'intersection_topology.json'
    participants = 'intersection_participants.jsonl'
    if comparison_id == 'official_control':
        if tamper:
            with TemporaryDirectory(prefix='c295149-device-tamper-') as temporary:
                substitute = Path(temporary)
                for name in ('intersection_topology.json',
                             'official_geometry_binding.json',
                             'official_device_context.json',
                             'official_device_states.jsonl', 'video_frames.jsonl'):
                    (substitute / name).write_bytes((right / name).read_bytes())
                modified = json.loads((substitute / 'official_device_context.json').read_text())
                modified['device_id'] = 'tampered-device'
                (substitute / 'official_device_context.json').write_text(json.dumps(modified) + '\n')
                _compare_official(left, substitute)
            raise AssertionError('Fixed-device tamper unexpectedly passed')
        measured = _compare_official(left, right)
        return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
                'source_receipts': [left_proof, right_proof], 'measurement': measured,
                'fixed_device_and_geometry_verified': True,
                'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}
    if tamper:
        with TemporaryDirectory(prefix='c295149-comparison-tamper-') as temporary:
            substitute = Path(temporary)
            (substitute / participants).write_bytes((right / participants).read_bytes())
            modified = json.loads((right / topology).read_text())
            modified['junction_id'] = 'tampered-junction'
            (substitute / topology).write_text(json.dumps(modified) + '\n')
            _compare_sources(comparison_id, left, substitute)
        raise AssertionError('Fixed-topology tamper unexpectedly passed')
    measured = _compare_sources(comparison_id, left, right)
    return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'source_receipts': [left_proof, right_proof], 'measurement': measured,
            'fixed_topology_verified': True, 'original_participants_verified': True,
            'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def _compare_sources(comparison_id, left, right):
    topology = 'intersection_topology.json'
    participants = 'intersection_participants.jsonl'
    if _sha(left / topology) != _sha(right / topology):
        raise ValueError('Controlled comparison changed fixed lane topology')
    first = []
    for root in (left, right):
        rows = [json.loads(line) for line in (root / participants).read_text().splitlines()]
        if not rows:
            raise ValueError('Controlled comparison lacks original participant frames')
        first.append(rows[0])
    for key in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if first[0].get(key) != first[1].get(key):
            raise ValueError('Controlled comparison changed initial actor setup: ' + key)
    a = measure(left / topology, left / participants)
    b = measure(right / topology, right / participants)
    if comparison_id == 'ending_yield_order':
        if not a['subject_entered_after_other_last_conflict_frame'] or b['subject_entered_after_other_last_conflict_frame']:
            raise ValueError('Original entry order did not change as selected')
    elif comparison_id == 'arrival_window':
        if a['entry_delta_s'] == b['entry_delta_s']:
            raise ValueError('Original arrival window did not change')
    return {'entry_delta_s': [a['entry_delta_s'], b['entry_delta_s']],
            'subject_entry_frame': [a['subject_entry_frame'], b['subject_entry_frame']],
            'other_entry_frame': [a['other_entry_frame'], b['other_entry_frame']],
            'legal_approximately_same_time': None}


def _compare_official(active, inoperative):
    fixed = ('intersection_topology.json', 'official_geometry_binding.json',
             'official_device_context.json')
    for name in fixed:
        if _sha(active / name) != _sha(inoperative / name):
            raise ValueError('Official comparison changed fixed source: ' + name)
    contexts = [json.loads((root / 'official_device_context.json').read_text())
                for root in (active, inoperative)]
    if contexts[0]['legal_official_status_claimed'] or contexts[1]['legal_official_status_claimed']:
        raise ValueError('Diagnostic device source cannot claim legal official status')
    states = []
    for root, context in zip((active, inoperative), contexts):
        rows = [json.loads(line) for line in
                (root / 'official_device_states.jsonl').read_text().splitlines()]
        frames = [json.loads(line) for line in
                  (root / 'video_frames.jsonl').read_text().splitlines()]
        if not rows or len(rows) != len(frames):
            raise ValueError('Official comparison lacks synchronized original state')
        if any(row['device_id'] != context['device_id'] or
               row['frame'] != frame['carla_frame'] or
               abs(row['time_s'] - frame['time_s']) > 1e-4
               for row, frame in zip(rows, frames)):
            raise ValueError('Official comparison changed device or frame join')
        values = {row['native_state'] for row in rows}
        if len(values) != 1:
            raise ValueError('Official comparison state changed within capture')
        states.append(next(iter(values)))
    if states != ['TrafficLightState.Red', 'TrafficLightState.Off']:
        raise ValueError('Official comparison did not isolate operating state')
    return {'native_states': states, 'device_id': contexts[0]['device_id'],
            'state_source_sha256': [_sha(root / 'official_device_states.jsonl')
                                    for root in (active, inoperative)],
            'legal_official_status': None}


def _audit_opposing_probe(manifest, spec, *, tamper):
    """Check the distinct-source exception probe without claiming a causal pair."""
    here = Path(__file__).resolve().parent
    suffix = spec['case_ids'][1].rsplit('__', 1)[-1]
    entry = next((row for row in manifest['cases'] if row['case_id'] == spec['case_ids'][1]), None)
    if entry is None:
        raise ValueError('Missing selected opposing-left case')
    tokens = shlex.split(entry['saved_processing_proof']['command'])
    original = Path(tokens[tokens.index('--attempt') + 1])
    receipt_path = here / entry['saved_processing_proof']['log']
    receipt = json.loads(receipt_path.read_text())
    if (not receipt.get('passed') or receipt.get('missing_evidence')
            or not receipt.get('recorded_only') or receipt.get('candidate_id') != 'primary'
            or receipt.get('case_id') != entry['case_id']
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']
            or _sha(receipt_path) != entry['saved_processing_proof']['log_sha256']
            or _sha(receipt['result']) != receipt['result_sha256']):
        raise ValueError('Opposing-left saved receipt differs')
    sources = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
               'video_frames.jsonl', 'trace.jsonl')
    for name in sources:
        if _sha(original / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Opposing-left original hash differs: ' + name)
    if tamper:
        with TemporaryDirectory(prefix='c295149-opposing-tamper-') as temporary:
            substitute = Path(temporary)
            for name in sources:
                (substitute / name).write_bytes((original / name).read_bytes())
            context = json.loads((substitute / sources[0]).read_text())
            context['opposite_route'][0]['heading_xy'] = [-1, 0]
            (substitute / sources[0]).write_text(json.dumps(context) + '\n')
            measure_opposing_left(substitute)
        raise AssertionError('Opposing-route tamper unexpectedly passed')
    measurement = measure_opposing_left(original)
    value = measurement['value']
    saved = json.loads((original / 'result.json').read_text())['measured_values']['opposing_left_observation']
    if value != saved or value['approach_heading_dot'] > -.8 or value['planned_left_cross'] < .5:
        raise ValueError('Opposing-left source measurement differs from saved result')
    return {'comparison_id': spec['comparison_id'], 'case_ids': spec['case_ids'],
            'comparison_kind': 'exception probe; topology differs by design',
            'opposing_source_receipt_sha256': _sha(receipt_path),
            'original_source_hashes': {name: _sha(original / name) for name in sources},
            'measurement': value, 'synthetic_diagnostic_only': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--tamper', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_exact(args.comparison, tamper=args.tamper)))
