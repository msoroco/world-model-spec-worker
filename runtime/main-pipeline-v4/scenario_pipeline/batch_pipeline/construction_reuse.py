"""Opt-in, hash-bound reuse within a prepared comparison group."""
from copy import deepcopy
import json
from .store import digest


def group_key(request):
    case = request['case']
    group = case.get('paired_probe_id') or case.get('sweep_id')
    return (request['cell']['cell_id'], request['actor'], group, case.get('target_law_id')) if group else None


def group_context(request, cases):
    key = group_key(request)
    members = [c for c in cases if group_key(dict(request, case=c)) == key] if key else [request['case']]
    return {'version': digest(members), 'cases': members,
            'policy': 'Explicitly support each member or fall back to independent construction. Preserve exceptions, recording requirements and deliberate differences.'}


def validate_contract(result, inputs):
    contract = result.get('reuse_contract')
    if contract is None:
        return
    group = inputs['construction_group']
    members = {c['case_id']: c for c in group['cases']}
    supported = contract.get('supported_case_ids', [])
    if (contract.get('group_version') != group['version'] or not supported or
            len(supported) != len(set(supported)) or not set(supported) <= set(members) or
            inputs['request']['case']['case_id'] not in supported):
        raise ValueError('Reuse contract must bind the frozen group and supported members')
    path = contract.get('config_file')
    files = {f['path']: f['content'] for f in result['files']}
    if path not in files or not path.endswith('.json') or not contract.get('capabilities'):
        raise ValueError('Reuse contract needs a JSON configuration file and stated capabilities')
    config = json.loads(files[path])
    request = inputs['request']
    if config.get('case') != request['case'] or config.get('actor') != request['actor'] or config.get('cell') != request['cell']:
        raise ValueError('Reusable configuration must contain the exact cell, actor and prepared case')
    for name in supported:
        if members[name]['recording_description'] != result['recording_description']:
            raise ValueError('Reusable members require identical recording descriptions')


def instantiate(inputs):
    """Return a new bundle, or None when explicit reuse support is absent."""
    if inputs['request'].get('repair_context'):
        return None
    anchor = inputs.get('comparison_anchor')
    if not anchor:
        return None
    source = anchor['construction']
    contract = source.get('reuse_contract', {})
    request = inputs['request']
    if (contract.get('group_version') != inputs['construction_group']['version'] or
            request['case']['case_id'] not in contract.get('supported_case_ids', [])):
        return None
    result = deepcopy(source)
    result.pop('repair', None)  # Its diagnosis remains on the referenced source artifact.
    config_file = next(f for f in result['files'] if f['path'] == contract['config_file'])
    config = json.loads(config_file['content'])
    config.update(cell=request['cell'], actor=request['actor'], case=request['case'])
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    result.update(cell_id=request['cell']['cell_id'], actor=request['actor'], case_id=request['case']['case_id'])
    result['implementation_reuse'] = {'source_artifact_id': anchor['artifact_id'],
        'source_bundle_version': digest(source), 'group_version': contract['group_version'],
        'implementation_version': digest([f for f in source['files'] if f['path'] != contract['config_file']]),
        'case_version': digest(request['case'])}
    return result


def refresh_pending(store, run, source_job):
    """Propagate an explicitly reusable correction only to never-driven members."""
    import time
    import uuid
    from . import stages
    source = store.job(source_job)
    if source['status'] != 'completed' or source['stage'] != 'construction':
        raise ValueError('A construction revision needs a completed source')
    bundle = store.artifact(source['artifact_id'])['payload']
    contract = bundle.get('reuse_contract')
    if not contract:
        return []
    key = group_key(json.loads(source['payload']))
    if key is None:
        return []
    owner = uuid.uuid4().hex
    impacts = []
    rows = store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution'", (run,)).fetchall()
    for row in rows:
        request = json.loads(row['payload'])
        if group_key(request) != key or request['case']['case_id'] not in contract['supported_case_ids']:
            continue
        impact = {'execution_job': row['id'], 'case_id': request['case']['case_id'], 'status': row['status']}
        impacts.append(impact)
        if row['status'] != 'pending' or row['attempts']:
            impact['action'] = 'retain_evidence_and_assess'  # Active runs finish their frozen bundle.
            continue
        parent = store.db.execute("SELECT j.* FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? AND j.stage='construction'", (row['id'],)).fetchone()
        if parent['id'] == source_job or parent['status'] != 'completed':
            impact['action'] = 'already_current_or_not_built'
            continue
        inputs, provenance = stages.input_context(store, run, dict(parent))
        inputs['comparison_anchor'] = {'artifact_id': source['artifact_id'], 'construction': bundle}
        revised = instantiate(inputs)
        if revised is None:
            impact['action'] = 'independent_construction_required'
            continue
        stages.validate('construction', revised, inputs)
        payload = dict(inputs['request'], construction_revision=source['artifact_id'])
        deps = [r[0] for r in store.db.execute('SELECT dependency_id FROM dependencies WHERE job_id=?', (parent['id'],))]
        with store.transaction():
            current = store.job(row['id'])
            if current['status'] != 'pending' or current['attempts']:
                impact['action'] = 'retain_evidence_and_assess'
                continue
            construction = stages.enqueue(store, run, 'construction', parent['entity'], parent['actor'], payload, deps)
            replacement = stages.enqueue(store, run, 'execution', row['entity'], row['actor'], request, [construction])
        claimed = store.claim(run, owner, ('construction',), job_ids=(construction,))
        if claimed:
            provenance = dict(provenance, corrected_source_artifact=source['artifact_id'])
            store.finish(claimed, owner, revised, provenance, {'adapter': 'configuration_reuse_revision'})
        impact.update(action='updated_pending', replacement_execution_job=replacement)
    store.db.execute('INSERT INTO events(job_id,created,message) VALUES(?,?,?)',
                     (source_job, time.time(), json.dumps({'construction_revision': source['artifact_id'], 'impacts': impacts})))
    return impacts
