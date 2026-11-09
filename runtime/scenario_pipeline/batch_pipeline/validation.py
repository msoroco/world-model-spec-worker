"""Mechanical evidence and coverage checks; never interpret a judgment standard."""
import math
from .sweeps import number


PROHIBITED = {'declaration', 'declaration_history', 'declaration_usage', 'declared_value', 'judgment_threshold',
              'legal_verdict', 'compliant', 'non_compliant', 'violating', 'compliance_label'}


def strip_null_prohibited_fields(value, path='$'):
    """Omit empty judgment placeholders without accepting any asserted value."""
    removed=[]
    if isinstance(value,dict):
        for key in list(value):
            child_path=path+'.'+str(key)
            if key in PROHIBITED and value[key] is None:
                del value[key]
                removed.append(child_path)
            else:
                removed.extend(strip_null_prohibited_fields(value[key],child_path))
    elif isinstance(value,list):
        for index,child in enumerate(value):
            removed.extend(strip_null_prohibited_fields(child,f'{path}[{index}]'))
    return removed


def equivalent_unit(left, right):
    aliases = {'meters': 'm', 'meter': 'm', 'seconds': 's', 'second': 's',
               'meters per second': 'm/s', 'feet': 'ft', 'radians': 'rad',
               'inverse meters': '1/m', 'category': 'categorical'}
    return aliases.get(left, left) == aliases.get(right, right)


def no_interpretations(value):
    if isinstance(value, dict):
        if PROHIBITED & value.keys():
            raise ValueError('Prohibited judgment interpretation or legal verdict')
        for child in value.values():
            no_interpretations(child)
    elif isinstance(value, list):
        for child in value:
            no_interpretations(child)


def observable_requirements(value):
    no_interpretations(value)
    allowed = {'observables', 'context_inputs', 'sweep_dimensions', 'landmarks', 'recording_needs', 'limitations'}
    if set(value) != allowed:
        raise ValueError('Observable requirements need only the value-free observation contract')
    for field in allowed:
        if not isinstance(value[field], list):
            raise ValueError('Observable requirements lists required')
    if not value['observables'] or not value['recording_needs'] or not value['limitations']:
        raise ValueError('Missing judgment evidence requirements or limitations')
    def value_free(v):
        if isinstance(v, (int, float, bool)):
            raise ValueError('Shared judgment requirements cannot contain selected numeric values or decisions')
        if isinstance(v, dict):
            if {'value', 'bound', 'operator', 'formula', 'rule', 'surrogate_pattern', 'threshold'} & v.keys():
                raise ValueError('Judgment requirements cannot define a predicate')
            for x in v.values(): value_free(x)
        elif isinstance(v, list):
            for x in v: value_free(x)
    value_free(value)
    for field in ('observables', 'context_inputs', 'sweep_dimensions', 'recording_needs'):
        names = []
        for item in value[field]:
            if any(not item.get(k) for k in ('name', 'unit', 'description')):
                raise ValueError('Named observable needs unit and description')
            names.append(item['name'])
        if len(names) != len(set(names)):
            raise ValueError('Duplicate observable requirements')
    for item in value['landmarks']:
        if any(not item.get(k) for k in ('name', 'description', 'source', 'verification_evidence')):
            raise ValueError('Reference landmark requires actual source verification')


def recording_description(value, requirements=()):
    if not isinstance(value, dict) or set(value) != {'channels', 'context_inputs', 'limitations'}:
        raise ValueError('Missing recording description')
    channels, contexts = value['channels'], value['context_inputs']
    if not isinstance(channels, list) or not channels or not isinstance(contexts, list) or not isinstance(value['limitations'], list):
        raise ValueError('Recording description needs channels/context/limitations')
    for item in channels:
        if any(not item.get(k) for k in ('name', 'unit', 'method', 'time_window', 'reference_frame', 'uncertainty')):
            raise ValueError('Incomplete recording channel')
        if not number(item.get('sampling_rate_hz')) or item['sampling_rate_hz'] <= 0:
            raise ValueError('Recording sampling rate must be positive for '+str(item.get('name'))+'; received '+str(item.get('sampling_rate_hz'))+'. Declare a numeric rate for time-varying/evaluated streams; setup-only snapshots belong in context_inputs.')
    for item in contexts:
        if any(not item.get(k) for k in ('name', 'unit', 'method')):
            raise ValueError('Incomplete recorded context')
    from .recording_views import views
    for item in channels+contexts: views(item)
    by_name = {v['name']: v for v in channels+contexts}
    if len(by_name) != len(channels)+len(contexts):
        raise ValueError('Duplicate recording channels/context')
    for requirement in requirements:
        for item in requirement['recording_needs']+requirement['context_inputs']:
            recorded = by_name.get(item['name'], {})
            representations = recorded.get('representation_units', [])
            described = item['unit'] in representations and any(word in item['unit'] for word in
                        ('categor', 'structured', 'metadata', 'native', 'description', 'record', 'text'))
            if not recorded or not (equivalent_unit(recorded['unit'], item['unit']) or described or item['unit'] in views(recorded)):
                raise ValueError('Recording omits required law observable/context: '+item['name'])


def numeric_thresholds(template, assignments=None):
    found = []
    def walk(value, path):
        if isinstance(value, dict):
            if {'variable', 'operator', 'value', 'unit'} <= value.keys():
                threshold_value = value['value']
                resolved = value
                if isinstance(threshold_value, str) and assignments:
                    parameter = assignments.get(threshold_value, {})
                    if parameter.get('kind') == 'world_setup' and equivalent_unit(parameter.get('unit'), value['unit']):
                        threshold_value = parameter.get('value')
                        resolved = dict(value, value=threshold_value, resolved_from=threshold_value if not isinstance(value['value'], str) else value['value'])
                if number(threshold_value):
                    found.append((path, resolved))
            for key, child in value.items():
                walk(child, path+'.'+key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path+'['+str(index)+']')
    for section in ('activation', 'obligation', 'timing'):
        walk(template['structure'][section], section)
    return found


def deterministic_branch(case, template):
    """Validate authored branch scope; never resolve a qualitative standard."""
    branch = case.get('deterministic_branch')
    if not isinstance(branch, dict):
        raise ValueError('Judgment-call compliance attempts need explicit deterministic branch context')
    clause = branch.get('source_clause')
    if not isinstance(clause, str) or not clause.strip() or clause not in template['quote']:
        raise ValueError('Deterministic branch needs an exact target-law source clause')
    expected = {(j['phrase'], j.get('note', '')) for j in template['structure']['judgment_calls_needed']}
    entries = branch.get('judgment_context', [])
    if len(entries) != len(expected) or {(j['phrase'], j.get('note', '')) for j in entries} != expected:
        raise ValueError('Deterministic branch must account for every judgment')
    for entry in entries:
        if entry.get('status') not in ('not_exercised', 'fixed_assumption') or not entry.get('reason'):
            raise ValueError('Unresolved judgment cannot receive a deterministic attempt label')
        refs = entry.get('world_setup_refs', [])
        if entry['status'] == 'fixed_assumption' and not refs:
            raise ValueError('Fixed judgment context needs explicit world setup')
        for name in refs:
            value = case['variable_assignments'].get(name, {})
            if value.get('kind') != 'world_setup' or value.get('value') is None:
                raise ValueError('Judgment context must reference fixed world setup assignments')
    return branch


def coverage(cases, binding, template_list, sweep_specs=()):
    from .sweeps import validate_spec
    active = {r['template_id'] for r in binding['law_refs']}
    templates = {t['template_id']: t for t in template_list if t['template_id'] in active}
    targeted = {}
    for case in cases:
        no_interpretations(case)
        if case['target_type'] == 'baseline':
            continue
        if case['target_type'] not in ('boundary_probe', 'compliant_attempt', 'violating_attempt', 'judgment_sweep'):
            raise ValueError('Unknown case target type')
        if not case.get('paired_probe_id') or 'deliberate_differences' not in case:
            raise ValueError('Non-baseline case needs comparison metadata')
        probe = case.get('probe', {})
        for field in ('primary_variable', 'comparison_or_standard', 'target_value_or_branch'):
            if field not in probe:
                raise ValueError('Missing probe metadata: '+field)
        if probe['primary_variable'] not in case['variable_assignments']:
            raise ValueError('Probe variable is not a canonical parameter')
        targeted.setdefault(case['target_law_id'], []).append(case)
    for spec in sweep_specs:
        validate_spec(spec)
        if spec['target_law_id'] not in {t['law_id'] for t in templates.values()}:
            raise ValueError('Sweep uses an inactive law')
    for key, template in templates.items():
        law_id = template['law_id']
        probes = targeted.get(law_id, [])
        judgments = template['structure']['judgment_calls_needed']
        assignments = probes[0].get('variable_assignments', {}) if probes else {}
        thresholds = numeric_thresholds(template, assignments)
        for path, threshold in thresholds:
            reference = threshold.get('resolved_from')
            if reference and any(c.get('variable_assignments', {}).get(reference) != assignments.get(reference) for c in probes):
                raise ValueError('Dynamic threshold setup differs across probes: '+reference)
        if judgments:
            branch_groups = {}
            for c in probes:
                if c['target_type'] in ('compliant_attempt', 'violating_attempt'):
                    branch = deterministic_branch(c, template)
                    branch_groups.setdefault(c['paired_probe_id'], []).append((c, branch))
            for group in branch_groups.values():
                if {c['target_type'] for c, _ in group} != {'compliant_attempt', 'violating_attempt'}:
                    raise ValueError('Deterministic branch needs a linked attempt pair')
                if any(branch != group[0][1] for _, branch in group):
                    raise ValueError('Deterministic comparison must hold judgment context fixed')
        for path, threshold in thresholds:
            matches = [c for c in probes if c.get('probe', {}).get('threshold_ref') == path]
            sides, pairs = set(), set()
            for c in matches:
                probe = c['probe']
                if c['target_type'] != 'boundary_probe' or not c.get('epsilon_used'):
                    raise ValueError('Numeric threshold needs explicit boundary probes and epsilon')
                if probe.get('operator') != threshold['operator'] or probe.get('unit') != threshold['unit']:
                    raise ValueError('Probe operator/unit differ from template')
                value = probe.get('test_value')
                if not number(value):
                    raise ValueError('Missing numeric probe value')
                from .speed_policy import probe_branch
                sides.add(probe_branch(c, threshold))
                pairs.add(c['paired_probe_id'])
            if sides != {'below', 'at', 'above'} or len(pairs) != 1:
                raise ValueError('Missing or unlinked below/at/above coverage: '+key+' '+path)
        if not judgments and not thresholds:
            if not {'compliant_attempt', 'violating_attempt'} <= {c['target_type'] for c in probes}:
                raise ValueError('Missing plain-rule attempt pair: '+key)
        identities = {(j['phrase'], j.get('note', '')) for j in judgments}
        covered = set()
        for spec in sweep_specs:
            if spec['target_law_id'] != law_id:
                continue
            refs = {(j['phrase'], j.get('note', '')) for j in spec['judgment_refs']}
            if not refs <= identities:
                raise ValueError('Sweep references an unknown judgment')
            covered.update(refs)
            if spec['status'] != 'complete':
                continue
            members = [c for c in probes if c.get('sweep_id') == spec['sweep_id']]
            if spec['planned_case_count'] != len(members):
                raise ValueError('Frozen sweep count mismatch')
            if [c['case_id'] for c in members] != spec['selection_order']:
                raise ValueError('Frozen sweep cases/order mismatch')
            if any(c.get('sweep_spec_version') != spec['spec_version'] for c in members):
                raise ValueError('Frozen sweep version mismatch')
            from .sweeps import grid
            if [c['sweep_point'] for c in members] != grid(spec):
                raise ValueError('Frozen sweep points changed')
            requirements = [j['observable_requirements'] for j in judgments
                            if (j['phrase'], j.get('note', '')) in refs]
            recording_description(spec.get('recording_description'), requirements)
            observed = {o['name']: o['unit'] for req in requirements for o in req['sweep_dimensions']}
            for axis in spec['axes']:
                if not equivalent_unit(observed.get(axis['observable']), axis['unit']):
                    raise ValueError('Sweep dimension lacks matching shared observable/unit')
                params = {v['name']: v for v in binding['variable_parameters']}
                if axis['observable'] not in params:
                    raise ValueError('Sweep observable is not a canonical binding parameter')
            for case in members:
                axes = {a['variable'] for a in spec['axes']}
                if set(case['deliberate_differences']) != axes:
                    raise ValueError('Sweep must hold all non-axis variables fixed')
                if any(case['variable_assignments'][name]['value'] != value for name, value in case['sweep_point'].items()):
                    raise ValueError('Sweep setpoint differs from its frozen point')
                if case['recording_description'] != spec['recording_description']:
                    raise ValueError('Sweep recording description changed')
                if not {phrase for phrase, _ in identities} <= set(case.get('unresolved_judgment_calls', [])):
                    raise ValueError('Judgment must remain unresolved')
        if covered != identities:
            raise ValueError('Missing judgment sweep plan: '+key)
        if not judgments and any(c['target_type'] == 'judgment_sweep' for c in probes):
            raise ValueError('Plain law cannot have a judgment sweep')


def recording_evidence(result, planned, artifact_path, sweep_measurements=()):
    """Validate saved machine-readable evidence against the frozen recording plan."""
    import json
    no_interpretations(result)
    recording_description(result.get('recording_description'))
    if result['recording_description'] != planned:
        raise ValueError('Execution recording description differs from construction')
    evidence = result.get('recording_evidence', [])
    by_name = {v['name']: v for v in evidence}
    if len(by_name) != len(evidence):
        raise ValueError('Duplicate recording evidence')
    streams = {}
    for channel in planned['channels']+planned['context_inputs']:
        item = by_name.get(channel['name'])
        if not item or item.get('unit') != channel['unit']:
            raise ValueError('Missing recording evidence: '+channel['name'])
        if item.get('missing_reason'):
            raise ValueError('Unconfirmed recording: '+channel['name']+' '+item['missing_reason'])
        path = artifact_path(item['reference'])
        if channel in planned['channels']:
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            if not rows or any(not number(r.get('time_s')) or 'value' not in r for r in rows):
                raise ValueError('Observable stream needs time_s and value')
            intervals = [b['time_s']-a['time_s'] for a, b in zip(rows, rows[1:])]
            if any(dt <= 0 or dt > 1.05/channel['sampling_rate_hz'] for dt in intervals):
                raise ValueError('Observable stream misses declared sampling rate')
            from .recording_views import verify
            verify(channel,rows)
            streams[channel['name']] = rows
            if any(r['value'] is None for r in rows):
                raise ValueError('Missing observable values')
        else:
            context = json.loads(path.read_text())
            from .recording_views import verify
            verify(channel,[context])
            if channel['name'] not in context or context[channel['name']] is None:
                raise ValueError('Missing authored instance context')
    for name, measured in result.get('realized_observables', {}).items():
        if any(not measured.get(k) for k in ('unit', 'method', 'time_window', 'statistic', 'reference')) or not number(measured.get('value')):
            raise ValueError('Incomplete realized observable summary')
        artifact_path(measured['reference'])
    for axis in sweep_measurements:
        name = axis['observable']
        summary = result.get('realized_observables', {}).get(name)
        definition = axis['measurement']
        if not summary or summary['unit'] != axis['unit'] or any(summary[k] != definition[k] for k in ('method', 'time_window', 'statistic')):
            raise ValueError('Realized sweep measurement differs from frozen definition')
        if name not in by_name or summary['reference'] != by_name[name]['reference']:
            raise ValueError('Realized sweep value lacks saved evidence')
        if name not in streams:
            context = json.loads(artifact_path(summary['reference']).read_text())
            if not number(context.get(name)) or context[name] != summary['value']:
                raise ValueError('Realized world-setup value contradicts recorded context')
            continue
        window = summary.get('sample_window_s')
        if not isinstance(window, list) or len(window) != 2 or not all(number(v) for v in window) or window[0] > window[1]:
            raise ValueError('Realized sweep summary needs actual sample_window_s')
        samples = [r['value'] for r in streams[name] if window[0] <= r['time_s'] <= window[1]]
        if not samples or not all(number(v) for v in samples):
            raise ValueError('No numeric samples in realized measurement window')
        statistics = {'min': min, 'max': max, 'mean': lambda v: sum(v)/len(v), 'first': lambda v: v[0], 'last': lambda v: v[-1]}
        actual = statistics[definition['statistic']](samples)
        if not math.isclose(actual, summary['value'], rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError('Realized sweep value contradicts saved observations')
