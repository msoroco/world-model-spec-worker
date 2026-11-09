"""Fixed physical sampling grids, selection order, and measured coverage; no labels."""
from collections import deque
from copy import deepcopy
from decimal import Decimal
from itertools import product
import math
import re
from .store import digest


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def axis_points(axis):
    for key in ('min', 'max', 'spacing'):
        if not number(axis.get(key)):
            raise ValueError('Sweep axis needs finite '+key)
    low, high, step = (Decimal(str(axis[k])) for k in ('min', 'max', 'spacing'))
    if high <= low or step <= 0:
        raise ValueError('Sweep range must increase and spacing must be positive')
    count = int((high-low)//step)
    values = [low+i*step for i in range(count+1)]
    if values[-1] != high:
        values.append(high)  # Last interval may be shorter; never omit the endpoint.
    return [float(v) for v in values]


def bisect_order(length):
    if length < 1:
        return []
    order = list(dict.fromkeys((0, length-1)))
    queue = deque([(0, length-1)])
    while queue:
        low, high = queue.popleft()
        if high-low <= 1:
            continue
        middle = (low+high)//2
        order.append(middle)
        queue.extend(((low, middle), (middle, high)))
    return order


def grid(spec):
    axes = spec['axes']
    values = [axis_points(a) for a in axes]
    indices = list(product(*(range(len(v)) for v in values)))
    if len(axes) == 1:
        order = [(i,) for i in bisect_order(len(values[0]))]
    else:
        corners = list(product(*((0, len(v)-1) for v in values)))
        center = tuple((len(v)-1)//2 for v in values)
        first = list(dict.fromkeys(corners+[center]))
        ranks = [{i: rank for rank, i in enumerate(bisect_order(len(v)))} for v in values]
        remaining = set(indices)-set(first)
        order = first+sorted(remaining, key=lambda ix: (max(r[i] for r, i in zip(ranks, ix)),
                            sum(r[i] for r, i in zip(ranks, ix)), ix))
    return [dict(zip((a['variable'] for a in axes), (v[i] for v, i in zip(values, ix)))) for ix in order]


def validate_spec(spec):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', spec.get('sweep_id', '')):
        raise ValueError('Sweep ID must be a simple name')
    for field in ('target_law_id', 'judgment_refs', 'rationale'):
        if not spec.get(field):
            raise ValueError('Missing sweep '+field)
    if spec.get('status') == 'incomplete':
        if not spec.get('missing_inputs'):
            raise ValueError('Incomplete sweep needs missing_inputs')
        return
    if spec.get('status') != 'complete' or not spec.get('axes'):
        raise ValueError('Sweep must be complete or explicitly incomplete')
    axes = spec['axes']
    if spec.get('spec_version'):
        original = {k: v for k, v in spec.items() if k not in ('spec_version', 'planned_case_count', 'selection_order')}
        if digest(original) != spec['spec_version']:
            raise ValueError('Frozen sweep specification changed')
    if spec.get('mode') != ('one_dimensional' if len(axes) == 1 else 'joint'):
        raise ValueError('Sweep mode differs from its axes')
    if len({a['variable'] for a in axes}) != len(axes):
        raise ValueError('Duplicate sweep axes')
    for axis in axes:
        for field in ('variable', 'observable', 'unit', 'range_rationale', 'spacing_rationale',
                      'feasibility_evidence', 'measurement'):
            if not axis.get(field):
                raise ValueError('Missing sweep axis '+field)
        for field in ('method', 'time_window', 'statistic'):
            if not axis['measurement'].get(field):
                raise ValueError('Missing sweep measurement '+field)
        if axis['measurement']['statistic'] not in ('min', 'max', 'mean', 'first', 'last'):
            raise ValueError('Sweep summaries use min/max/mean/first/last; retain the full raw stream')
        axis_points(axis)
    if not isinstance(spec.get('landmarks'), list):
        raise ValueError('Sweep must document landmarks, including an empty list if unavailable')
    for landmark in spec['landmarks']:
        if any(not landmark.get(k) for k in ('name', 'source', 'verification_evidence', 'purpose')):
            raise ValueError('Landmark requires actual source evidence and coverage-only purpose')
        if landmark['purpose'] != 'coverage_landmark':
            raise ValueError('Landmark cannot be a judgment threshold')


def expand_sweeps(result, templates=(), bindings=None):
    """Normalize a worker's compact specifications into complete frozen cases once."""
    if result.get('sweeps_expanded'):
        return
    if not isinstance(result.get('cases'), list):
        raise ValueError('Cases response requires a cases list')
    # Accept qualified template paths without changing threshold semantics.
    # Normalize only an exact known template prefix and retain an audit record.
    for case in result['cases']:
        probe = case.get('probe', {})
        reference = probe.get('threshold_ref', '')
        for template in templates:
            prefixes = (template['template_id']+'.structure.', template['law_id']+'.structure.')
            prefix = next((p for p in prefixes if reference.startswith(p)), None)
            if case.get('target_law_id') == template['law_id'] and prefix:
                probe['threshold_ref'] = reference[len(prefix):]
                result.setdefault('case_contract_normalizations', []).append({
                    'case_id': case['case_id'], 'field': 'probe.threshold_ref',
                    'source': reference, 'canonical': probe['threshold_ref']})
                break
        if 'epsilon_used' in probe and 'epsilon_used' not in case:
            case['epsilon_used'] = deepcopy(probe['epsilon_used'])
            result.setdefault('case_contract_normalizations', []).append({
                'case_id': case['case_id'], 'field': 'epsilon_used',
                'source': 'probe.epsilon_used', 'canonical': 'case.epsilon_used'})
    defaults = result.pop('case_defaults', {})
    if not isinstance(defaults, dict) or set(defaults)-{'variable_assignments', 'recording_description'}:
        raise ValueError('Case defaults contain only assignments and recording_description')
    for item in result['cases']+list(result.get('sweep_specs', [])):
        if item.get('status') == 'incomplete':
            continue
        assignments = deepcopy(defaults.get('variable_assignments', {}))
        assignments.update(item.get('variable_assignments', {}))
        fixed = {p['name']: p['value'] for p in (bindings or {}).get('fixed_parameters', [])}
        variable_names = {p['name'] for p in (bindings or {}).get('variable_parameters', [])}
        for name in set(assignments) & set(fixed) - variable_names:
            assignment = assignments[name]
            if isinstance(assignment, dict) and assignment.get('kind') == 'world_setup' and digest(assignment.get('value')) == digest(fixed[name]):
                result.setdefault('case_contract_normalizations', []).append({
                    'case_id': item.get('case_id', item.get('sweep_id')),
                    'field': 'variable_assignments.'+name, 'source': assignment,
                    'canonical': 'unchanged binding.fixed_parameters.'+name})
                del assignments[name]
        item['variable_assignments'] = assignments
        if not item.get('recording_description') and 'recording_description' in defaults:
            item['recording_description'] = deepcopy(defaults['recording_description'])
    for case in result['cases']:
        if any(key not in case for key in ('case_id', 'target_law_id', 'target_type',
                                          'rationale', 'variable_assignments',
                                          'recording_description', 'unresolved_judgment_calls')):
            raise ValueError('Ordinary cases require case_id, target_law_id, target_type, rationale, assignments, recording_description and unresolved_judgment_calls')
    ids = {c['case_id'] for c in result['cases']}
    seen = set()
    for spec in result.setdefault('sweep_specs', []):
        # Notes are source identity, not a place for the planner to rewrite residue.
        # A unique exact law/phrase reference can be linked mechanically; ambiguity
        # still requires the exact source note and fails rather than guessing.
        for ref in spec.get('judgment_refs', []):
            entries = [j for t in templates if t['law_id'] == spec['target_law_id']
                       for j in t['structure']['judgment_calls_needed'] if j['phrase'] == ref['phrase']]
            if len(entries) == 1 and ref.get('note', '') != entries[0].get('note', ''):
                result.setdefault('reference_normalizations', []).append({
                    'sweep_id': spec['sweep_id'], 'phrase': ref['phrase'],
                    'planner_note': ref.get('note', ''), 'source_note': entries[0].get('note', '')})
                ref['note'] = entries[0].get('note', '')
        validate_spec(spec)
        if spec['sweep_id'] in seen:
            raise ValueError('Duplicate sweep ID')
        seen.add(spec['sweep_id'])
        if spec['status'] == 'incomplete':
            continue
        frozen = deepcopy(spec)
        points = grid(spec)
        version = digest(frozen)
        spec['spec_version'] = version
        spec['planned_case_count'] = len(points)
        spec['selection_order'] = []
        for rank, point in enumerate(points):
            case_id = spec['sweep_id']+'-'+str(rank).zfill(4)
            if case_id in ids:
                raise ValueError('Sweep case ID collision')
            ids.add(case_id)
            assignments = deepcopy(spec['variable_assignments'])
            for name, value in point.items():
                if name not in assignments or assignments[name]['kind'] not in ('controller', 'world_setup'):
                    raise ValueError('Sweep must vary an authored fact or controller target')
                assignments[name]['value'] = value
                assignments[name]['note'] = 'Fixed physical sweep setpoint; actual behavior is measured separately'
            spec['selection_order'].append(case_id)
            result['cases'].append({'case_id': case_id, 'target_law_id': spec['target_law_id'],
                'target_type': 'judgment_sweep', 'rationale': spec['rationale'],
                'paired_probe_id': spec['sweep_id'], 'deliberate_differences': list(point),
                'probe': {'primary_variable': spec['axes'][0]['variable'],
                          'comparison_or_standard': 'physical coverage; legal judgment unresolved',
                          'target_value_or_branch': point},
                'sweep_id': spec['sweep_id'], 'sweep_spec_version': version, 'sweep_point': point,
                'selection_rank': rank, 'variable_assignments': assignments,
                'recording_description': deepcopy(spec['recording_description']),
                'sweep_measurements': [{'observable': a['observable'], 'unit': a['unit'], 'measurement': deepcopy(a['measurement'])} for a in spec['axes']],
                'unresolved_judgment_calls': sorted({j['phrase'] for t in templates if t['law_id'] == spec['target_law_id'] for j in t['structure']['judgment_calls_needed']} or {j['phrase'] for j in spec['judgment_refs']})})
    from .speed_policy import apply_speed_policy
    apply_speed_policy(result['cases'], templates)
    result['sweeps_expanded'] = True


def realized_coverage(spec, records, completion_policy=None):
    """Records are selected cases with status and zero or more retained attempts."""
    complete = spec.get('status') == 'complete'
    planned = spec.get('selection_order', [])
    output = {'sweep_id': spec['sweep_id'], 'spec': spec,
              'planned': len(planned), 'selected': len(records),
              'unselected': len(set(planned)-{r['case_id'] for r in records}),
              'executions': records, 'axes': [], 'joint_realized_points': [],
              'limitations': ['Finite sampling does not guarantee both labels for a later predicate.'],
              'status': 'planned' if complete else 'incomplete'}
    joint = []
    for axis in spec.get('axes', []) if complete else []:
        values, missing = [], []
        for record in records:
            for attempt in record.get('attempts', []):
                measured = attempt.get('realized_observables', {}).get(axis['observable'])
                if measured and number(measured.get('value')) and measured.get('unit') == axis['unit']:
                    values.append(measured['value'])
                else:
                    missing.append({'case_id': record['case_id'], 'attempt': attempt.get('attempt')})
        unique = sorted(set(values))
        inside = [v for v in unique if axis['min'] <= v <= axis['max']]
        bounds = sorted(set([axis['min'], axis['max']]+inside))
        gaps = [{'from': a, 'to': b, 'width': b-a} for a, b in zip(bounds, bounds[1:])]
        output['axes'].append({'observable': axis['observable'], 'unit': axis['unit'],
            'measurement': axis['measurement'], 'realized_values': unique,
            'outside_planned_range': [v for v in unique if v not in inside],
            'gaps': gaps,
            'largest_gap': max((g['width'] for g in gaps), default=0), 'missing_measurements': missing})
    for record in records:
        for attempt in record.get('attempts', []):
            point = {a['observable']: attempt.get('realized_observables', {}).get(a['observable'])
                     for a in spec.get('axes', [])}
            if point and all(v and number(v.get('value')) for v in point.values()):
                joint.append({'case_id': record['case_id'], 'attempt': attempt.get('attempt'), 'values': point})
    output['joint_realized_points'] = joint
    if completion_policy:
        output['completion_acceptance'] = completion_acceptance(spec, records)
    return output


def completion_acceptance(spec, records):
    """Judge maneuver completion, never legal compliance; retain every attempt."""
    result = {'status': 'pending', 'endpoint_incomplete': {'minimum': 0, 'maximum': 0},
              'interior_incomplete': 0, 'violations': [], 'pending_cases': []}
    if spec.get('status') != 'complete':
        result['status'] = 'incomplete_plan'
        return result
    axes = spec['axes']
    if len(axes) != 1:
        result.update(status='failed', violations=['Endpoint-only allowance requires a one-dimensional sweep'])
        return result
    axis = axes[0]
    selected = {r['case_id'] for r in records}
    result['pending_cases'].extend(sorted(set(spec.get('selection_order', []))-selected))
    for record in records:
        value = record.get('requested', {}).get(axis['variable'])
        endpoint = 'minimum' if value == axis['min'] else 'maximum' if value == axis['max'] else None
        attempts = record.get('attempts', [])
        if not attempts or record.get('status') in ('pending','running'):
            result['pending_cases'].append(record['case_id'])
        for attempt in attempts:
            if attempt.get('maneuver_completed') is True:
                continue
            if attempt.get('maneuver_completed') is not False:
                result['violations'].append({'case_id': record['case_id'], 'attempt': attempt.get('attempt'), 'reason': 'Missing maneuver completion evidence'})
            elif endpoint:
                result['endpoint_incomplete'][endpoint] += 1
                if not any(v is True for k, v in attempt.get('physical_failure_flags', {}).items()
                           if k not in ('detection_validated', 'detector_validated')) or not attempt.get('termination_reason'):
                    result['violations'].append({'case_id': record['case_id'], 'reason': 'Endpoint incompletion lacks physical cause evidence'})
            else:
                result['interior_incomplete'] += 1
                result['violations'].append({'case_id': record['case_id'], 'attempt': attempt.get('attempt'), 'reason': 'Interior maneuver incomplete'})
    for endpoint, count in result['endpoint_incomplete'].items():
        if count > 1:
            result['violations'].append({'endpoint': endpoint, 'reason': 'More than one incomplete endpoint attempt'})
    result['pending_cases']=sorted(set(result['pending_cases']))
    result['status'] = 'failed' if result['violations'] else 'pending' if result['pending_cases'] else 'passed'
    return result
