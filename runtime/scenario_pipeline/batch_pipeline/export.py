"""Organized JSON snapshots and progress from authoritative database queries."""
import html
import json
import os
from pathlib import Path
from .store import atomic
from workspaces import semantic_directory, artifact_directory
from .stages import run_info, catalog, actors


def _sweep_reports(rows, artifact_map, attempts, stale, info):
    from .sweeps import realized_coverage
    sweep_reports = []
    for row in rows:
        if row['stage'] != 'cases' or not row['active'] or not row['artifact_id'] or row['id'] in stale:
            continue
        data = artifact_map[row['artifact_id']]['payload']
        for spec in data.get('sweep_specs', []):
            records = []
            by_case = {}
            for execution in rows:
                if execution['stage'] != 'execution' or execution['actor'] != row['actor']:
                    continue
                request = json.loads(execution['payload'])
                case = request.get('case', {})
                if request.get('cell', {}).get('cell_id') != row['entity'] or case.get('sweep_id') != spec['sweep_id'] or case.get('sweep_spec_version') != spec.get('spec_version'):
                    continue
                captured = []
                for attempt in attempts:
                    if attempt['job_id'] != execution['id']:
                        continue
                    item = {'attempt': attempt['number'], 'job_id':execution['id'], 'active_construction':bool(execution['active']), 'error': attempt['error'],
                            'directory': attempt['metadata'].get('directory'), 'realized_observables': {}}
                    if execution['artifact_id'] and attempt['number'] == execution['attempts']:
                        payload = artifact_map[execution['artifact_id']]['payload']
                        item.update(realized_observables=payload.get('realized_observables', {}),
                                    video_references=payload.get('video_references', []),
                                    directory=item.get('directory') or payload.get('attempt_directory'),
                                    termination_reason=payload.get('termination_reason'),
                                    physical_failure_flags=payload.get('physical_failure_flags'),
                                    maneuver_completed=payload.get('maneuver_completed'),
                                    situation_confirmed=payload.get('situation_confirmed'),
                                    recording_description=payload.get('recording_description'))
                    if 'maneuver_completed' not in item and item.get('directory'):
                        saved = Path(item['directory'])/'result.json'
                        if saved.exists():
                            retained = json.loads(saved.read_text())
                            for field in ('maneuver_completed','termination_reason','physical_failure_flags'):
                                item[field] = retained.get(field)
                    if item.get('directory'):
                        from .failure_diagnosis import diagnosed_flags
                        diagnosis=diagnosed_flags(item['directory'])
                        if diagnosis:
                            flags=dict(item.get('physical_failure_flags') or {})
                            for name,value in diagnosis['flags'].items():flags[name]=bool(flags.get(name) or value)
                            item['physical_failure_flags']=flags;item['additive_physical_failure_diagnosis']=diagnosis
                    captured.append(item)
                record=by_case.get(case['case_id'])
                if record is None:
                    record={'case_id':case['case_id'],'status':execution['status'],
                            'requested':case.get('sweep_point'),'attempts':[]}
                    by_case[case['case_id']]=record;records.append(record)
                record['attempts'].extend(captured)
                if execution['active']:record['status']=execution['status']
            report = realized_coverage(spec, records, info['config'].get('judgment_completion_policy'))
            report.update(cell_id=row['entity'], actor=row['actor'])
            sweep_reports.append(report)
    return sweep_reports


def export(store, run, artifacts=True):
    info = run_info(store, run)
    out = Path(info['output'])
    atomic(out/'run.json', {k: v for k, v in info.items() if k != 'config'} |
           {'config': {k: v for k, v in info['config'].items() if k != 'summaries'}})
    source = catalog(store, run)
    if not (out/'inputs/vocabulary_catalog.json').exists():
        atomic(out/'inputs/vocabulary_catalog.json', source)
    library = store.db.execute('SELECT template_id,payload,version FROM templates ORDER BY template_id').fetchall()
    versions = {r['template_id']: r['version'] for r in library}
    templates = [json.loads(r['payload']) for r in library]
    if artifacts:
        atomic(out/'shared/law_templates.json', {'status': 'draft', 'templates': templates})
        atomic(out/'shared/context_predicates.json', info['config'].get('context_predicates', {}))
    rows = store.db.execute('SELECT j.*,r.active FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? ORDER BY j.id', (run,)).fetchall()
    dependencies = {}
    for row in store.db.execute('SELECT d.job_id,p.id,p.status,p.error FROM dependencies d JOIN jobs p ON p.id=d.dependency_id JOIN run_jobs r ON r.job_id=d.job_id WHERE r.run_id=?', (run,)):
        dependencies.setdefault(row['job_id'], []).append({'job_id': row['id'], 'status': row['status'], 'error': row['error']})
    # A single join avoids one query per artifact at catalog scale.
    artifact_map = {}
    for row in store.db.execute('SELECT a.* FROM artifacts a JOIN run_jobs r ON r.job_id=a.job_id WHERE r.run_id=?', (run,)):
        artifact_map[row['id']] = dict(row, payload=json.loads(row['payload']), provenance=json.loads(row['provenance']))
    stale = set()
    for row in rows:
        if row['artifact_id']:
            consumed = artifact_map[row['artifact_id']]['provenance'].get('template_versions', {})
            if any(versions.get(k) != v for k, v in consumed.items()):
                stale.add(row['id'])
    # Include all transitive dependents, even if creation order was non-topological.
    changed = True
    while changed:
        before = len(stale)
        stale.update(row['id'] for row in rows if any(d['job_id'] in stale for d in dependencies.get(row['id'], [])))
        changed = before != len(stale)
    counts, entries, attempts = {}, [], []
    selected_cells, selected_actors, case_count, probe_groups = set(), set(), 0, set()
    for row in rows:
        j = dict(row)
        payload = json.loads(j['payload'])
        failures = [d for d in dependencies.get(j['id'], []) if d['status'] in ('failed', 'blocked')]
        state = 'superseded' if not j['active'] else 'stale' if j['id'] in stale else 'blocked' if j['status'] == 'pending' and failures else j['status']
        counts.setdefault(j['stage'], {})[state] = counts.setdefault(j['stage'], {}).get(state, 0)+1
        if j['stage'] == 'relevance' and j['active']:
            selected_cells.add(j['entity']); selected_actors.add((j['entity'], j['actor']))
        link = None
        if j['artifact_id']:
            artifact = artifact_map[j['artifact_id']]
            data = artifact['payload']
            if j['stage'] == 'relevance_batch':
                path = semantic_directory(out,payload['cell']['cell_id'],j['actor'])/'relevance_batches'/(str(j['id'])+'.json')
            elif j['stage'] in ('relevance', 'bindings', 'cases'):
                path = semantic_directory(out,j['entity'],j['actor'])/(j['stage']+'.json')
            elif j['stage'] in ('construction', 'execution'):
                path = artifact_directory(out,payload.get('cell',{}).get('cell_id',j['entity']),j['actor'],payload.get('case',{}),j['id'])/(j['stage']+'.json')
            else:
                path = out/'shared/artifacts'/(str(j['id'])+'.json')
            if artifacts and (j['active'] or j['stage'] not in ('relevance', 'bindings', 'cases')):
                atomic(path, dict(data, artifact_metadata={'artifact_id': artifact['id'], 'review_status': artifact['review_status'],
                       'reviewed_at': artifact['reviewed_at'], 'stale': j['id'] in stale, 'provenance': artifact['provenance']}))
            link = os.path.relpath(path, out) if path.exists() else None
            if j['stage'] == 'cases' and state not in ('stale', 'superseded'):
                case_count += len(data['cases'])
                probe_groups.update((j['entity'], j['actor'], c['paired_probe_id']) for c in data['cases'] if c.get('paired_probe_id'))
        entries.append({'job_id': j['id'], 'stage': j['stage'], 'entity': j['entity'], 'actor': j['actor'],
                        'status': state, 'attempts': j['attempts'], 'error': j['error'], 'blocked_by': failures, 'artifact': link})
    totals = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
    for r in store.db.execute('SELECT a.* FROM attempts a JOIN run_jobs r ON r.job_id=a.job_id WHERE r.run_id=? ORDER BY a.id', (run,)):
        a = dict(r, metadata=json.loads(r['metadata']) if r['metadata'] else {})
        attempts.append(a)
        usage = a['metadata'].get('usage', [])
        for item in [usage] if isinstance(usage, dict) else usage:
            for k in totals:
                totals[k] += item.get(k, 0) or 0
    sweep_reports = _sweep_reports(rows, artifact_map, attempts, stale, info)

    eligible = sum(bool(actors(c)) for c in source['cells'])
    judgments = [j for t in templates for j in t['structure']['judgment_calls_needed']]
    progress = {'run_id': run, 'catalog_cells': len(source['cells']), 'actor_eligible_cells': eligible,
                'selected_cells': len(selected_cells), 'selected_cell_actors': len(selected_actors),
                'current_cases': case_count, 'current_probe_groups': len(probe_groups),
                'shared_templates': len(templates), 'shared_judgments': len(judgments),
                'judgments_with_observable_requirements': sum(bool(j.get('observable_requirements')) for j in judgments),
                'sweeps': sweep_reports,
                'recorded_token_usage': totals, 'attempt_count': len(attempts),
                'stages': counts, 'jobs': entries, 'attempts': attempts,
                'simulation_policy': 'Fixed coarse-to-fine selection; default three attempts per selected sweep. Unrun points are unselected.'}
    atomic(out/'progress.json', progress)
    if artifacts:
        atomic(out/'logs/attempts.json', attempts)
    if artifacts:
        atomic(out/'sweep_coverage.json', {'status': 'draft', 'sweeps': sweep_reports})
    header = ''.join('<tr><td>'+html.escape(stage)+'</td><td>'+html.escape(json.dumps(states, sort_keys=True))+'</td></tr>' for stage, states in counts.items())
    # Keep the browser usable: full searchable data lives in progress.json.
    preview = sorted(entries, key=lambda e: (e['status'] not in ('failed', 'blocked', 'stale'), e['job_id']))[:500]
    body = ''.join('<tr><td>'+str(e['job_id'])+'</td><td>'+html.escape(e['stage'])+'</td><td>'+html.escape(e['entity']+' / '+e['actor'])+'</td><td>'+html.escape(e['status'])+'</td><td>'+('<a href="'+html.escape(e['artifact'], quote=True)+'">artifact</a>' if e['artifact'] else html.escape(e['error'] or json.dumps(e['blocked_by'])))+'</td></tr>' for e in preview)
    sweep_html = ''
    for report in sweep_reports:
        video_links = []
        for execution in report['executions']:
            for attempt in execution['attempts']:
                for video in attempt.get('video_references', []):
                    path = Path(video)
                    if not path.is_absolute(): path = Path(attempt['directory'])/path
                    video_links.append('<a href="'+html.escape(os.path.relpath(path, out), quote=True)+'">'+html.escape(execution['case_id'])+' video</a>')
        sweep_html += '<h3>'+html.escape(report['cell_id']+' / '+report['actor']+' / '+report['sweep_id'])+'</h3><p>'+str(report['planned'])+' planned; '+str(report['selected'])+' selected; '+str(report['unselected'])+' unselected.</p><pre>'+html.escape(json.dumps(report['axes'], indent=2))+'</pre><p>'+' | '.join(video_links)+'</p>'
    (out/'progress.html').write_text('<!doctype html><meta charset="utf-8"><title>Pipeline progress</title><style>body{font:16px sans-serif;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}input{padding:8px}</style>'
        '<h1>Run '+html.escape(run)+'</h1><p>'+str(len(source['cells']))+' catalog cells; '+str(len(selected_cells))+' selected cells; '+str(len(selected_actors))+' selected cell/actor pairs. Review is informational.</p>'
        '<p>Stage counts use their own job denominators. Unselected simulations are not incomplete. Stale artifacts and historical executions are retained.</p><table><tr><th>Stage</th><th>Job counts</th></tr>'+header+
        '</table><h2>Measured sweep coverage</h2>'+sweep_html+'<h2>Jobs</h2><p>Showing up to 500 jobs, failures first. <a href="progress.json">All jobs and attempts (JSON)</a></p><input placeholder="Filter displayed jobs" oninput="document.querySelectorAll(\'tbody tr\').forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(this.value.toLowerCase()))"><table><thead><tr><th>ID</th><th>Stage</th><th>Entity / actor</th><th>Status</th><th>Evidence / error</th></tr></thead><tbody>'+body+'</tbody></table>')
    return progress


def scoped_sweep_reports(store, run, cells, actor):
    """Read only requested cells; never materialize campaign-wide reports."""
    cells=tuple(sorted(set(cells)))
    if not cells:return []
    marks=','.join('?' for _ in cells)
    predicate="r.run_id=? AND j.actor=? AND ((j.stage='cases' AND j.entity IN ("+marks+")) OR (j.stage='execution' AND json_extract(j.payload,'$.cell.cell_id') IN ("+marks+")))"
    params=(run,actor,*cells,*cells)
    rows=list(store.db.execute('SELECT j.*,r.active FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE '+predicate,params))
    artifacts={}
    for row in store.db.execute('SELECT a.* FROM artifacts a JOIN jobs j ON j.id=a.job_id JOIN run_jobs r ON r.job_id=j.id WHERE '+predicate,params):
        artifacts[row['id']]=dict(row,payload=json.loads(row['payload']),provenance=json.loads(row['provenance']))
    attempts=[dict(row,metadata=json.loads(row['metadata']) if row['metadata'] else {}) for row in store.db.execute(
        'SELECT a.* FROM attempts a JOIN jobs j ON j.id=a.job_id JOIN run_jobs r ON r.job_id=j.id WHERE '+predicate,params)]
    versions=dict(store.db.execute('SELECT template_id,version FROM templates'))
    stale={row['id'] for row in rows if row['artifact_id'] and any(versions.get(k)!=v for k,v in artifacts[row['artifact_id']]['provenance'].get('template_versions',{}).items())}
    return _sweep_reports(rows,artifacts,attempts,stale,run_info(store,run))
