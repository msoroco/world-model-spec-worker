#!/usr/bin/env python3
"""Build, execute, and adapt selected cells sequentially, validating the first case.

Requires an imported run with completed cases and an already-running dedicated
CARLA endpoint. No server launch or target/budget changes. Failed cases receive diagnosed construction repairs.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from batch_pipeline import stages
from batch_pipeline.store import Store, atomic
from batch_pipeline.runner import run
from batch_pipeline.carla import execute
from pipeline import choose_simulation
from workspaces import semantic_directory


def selected_incomplete_plans(specs, cases, selected):
    """Unselected future judgment plans cannot fail accepted deterministic cases."""
    groups={c.get('sweep_id') for c in cases if c['case_id'] in selected}
    return [s['sweep_id'] for s in specs if s['status']!='complete' and s['sweep_id'] in groups]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--run',required=True)
    parser.add_argument('--cell',action='append',required=True)
    parser.add_argument('--case',action='append',default=[],help='Execute only these case IDs after the cell has a validated original capture')
    parser.add_argument('--actor',default='motor_vehicle_driver')
    parser.add_argument('--recorded-only',action='store_true',help='Finalize already selected recordings; never construct, drive or repair')
    parser.add_argument('--production',action='store_true',help='Four verdicts with measured reference checks; unsupported checks do not reject adequate evidence')
    parser.add_argument('--include-baselines',action='store_true',help='Also simulate neutral baseline definitions')
    parser.add_argument('--cell-run',action='append',default=[],help='CELL=RUN for an explicitly authored context variant')
    parser.add_argument('--cell-inventory',action='append',default=[],help='CELL=PATH to verified physical resource evidence for each construction')
    parser.add_argument('--python',required=True)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=22000)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--validator',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=900)
    parser.add_argument('--max-repairs',type=int,default=2,help='Diagnosed repairs per case; unchanged replay is prohibited')
    args=parser.parse_args()
    if args.max_repairs<0:raise ValueError('--max-repairs cannot be negative')
    cell_runs=dict(item.split('=',1) for item in args.cell_run)
    inventories={cell:json.loads(Path(path).read_text()) for cell,path in (item.split('=',1)for item in args.cell_inventory)}
    store=Store(args.db)
    info=stages.run_info(store,args.run)
    output=Path(info['output'])
    worker=info['config']['model']['worker_argv']
    project=Path(__file__).resolve().parent.parent
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join(map(str,(project/'scenario_pipeline',project/'scripts',project/'third_party/carla_scene_graphs')))+os.pathsep+env.get('PYTHONPATH','')
    index_path=output/'delivery_index.json'
    delivery=json.loads(index_path.read_text()) if index_path.exists() else {'status':'running','run_id':args.run,'cells':[],'expected_cells':args.cell}
    delivery['expected_cells'] = [r[0] for r in store.db.execute("SELECT DISTINCT j.entity FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='relevance' ORDER BY j.entity", (args.run,))]
    if args.recorded_only:
        expected=sorted({(json.loads(r[0])['cell']['cell_id'],r[1]) for r in store.db.execute(
            "SELECT j.payload,j.actor FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution'",(args.run,))})
        delivery['expected_cells']=sorted({cell for cell,actor in expected})
        delivery['expected_cell_actors']=[{'cell_id':cell,'actor':actor} for cell,actor in expected]
    if info['config'].get('explicit_repair_selection'):
        delivery['expected_cells']=list(info['config']['explicit_repair_selection'])
        delivery['explicit_repair_selection']=info['config']['explicit_repair_selection']
    delivery['baseline_simulation']=args.include_baselines
    def refresh():
        atomic(index_path,delivery)
    try:
        for cell in args.cell:
            current_run=cell_runs.get(cell,args.run)
            worker=stages.run_info(store,current_run)['config']['model']['worker_argv']
            entry=next((e for e in delivery['cells'] if e['cell_id']==cell and e.get('actor','motor_vehicle_driver')==args.actor),None)
            if entry is None:
                entry={'cell_id':cell,'actor':args.actor,'run_id':current_run,'status':'pending','cases':[]}
                delivery['cells'].append(entry)
            if entry.get('run_id',args.run)!=current_run:
                raise ValueError('Cannot change an already selected cell context in delivery index')
            rows=store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='cases' AND j.entity=? AND j.actor=? AND j.status='completed'",(current_run,cell,args.actor)).fetchall()
            if len(rows)!=1:
                entry.update(status='blocked',error='Expected one completed current case set');refresh();continue
            artifact=store.artifact(rows[0]['artifact_id']);data=artifact['payload']
            # Materialize only this cell's current definition, never the campaign.
            definition_path=semantic_directory(stages.run_info(store,current_run)['output'],cell,args.actor)/'cases.json'
            if not definition_path.exists():atomic(definition_path,data)
            incomplete=[s['sweep_id'] for s in data.get('sweep_specs',[]) if s['status']!='complete']
            entry['incomplete_plans']=incomplete
            cases=[c for c in data['cases'] if args.include_baselines or c['target_type']!='baseline']
            entry['planned_cases']=len(cases)
            if args.recorded_only:
                selected={json.loads(r[0])['case']['case_id'] for r in store.db.execute(
                    "SELECT j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.actor=?",(current_run,args.actor))
                    if json.loads(r[0])['cell']['cell_id']==cell}
                cases=[c for c in data['cases'] if args.include_baselines or c['target_type']!='baseline' or c['case_id'] in selected]
                entry['planned_cases']=len(cases)
                for case in cases:
                    saved=next((c for c in entry['cases'] if c['case_id']==case['case_id']),None)
                    state='pending' if case['case_id'] in selected else 'unselected'
                    if saved is None:
                        entry['cases'].append({'case_id':case['case_id'],'status':state,
                            'group_id':case.get('paired_probe_id') or case.get('sweep_id') or case['target_law_id']})
                    elif saved.get('status')=='unselected' and state=='pending':saved['status']=state
            if args.case:
                selected = set(args.case)
                known = {c['case_id'] for c in cases}
                if len(args.cell) != 1 or not selected <= known:
                    raise ValueError('--case requires one cell and case IDs from its current frozen plan')
                # The first selected actual probe establishes the capture gate.
            def variant(case):
                cap=case.get('target_law_id')=='NRS-484B-600-1e'
                return 'unsigned_cap' if cap and cell=='C230289' else 'extended_speed' if cap and cell in ('C329610','C245490') else 'default'
            definitions={c['case_id']:c for c in cases}
            capture_gates={variant(definitions[c['case_id']]) for c in entry['cases'] if c['case_id'] in definitions and c.get('capture_validated') and c.get('decoder_passed')}
            for number,case in enumerate(cases):
                if args.recorded_only and case['case_id'] not in selected:
                    continue
                if args.case and case['case_id'] not in selected:
                    continue
                case_entry=next((c for c in entry['cases'] if c['case_id']==case['case_id']),None)
                current_execution=store.db.execute("SELECT j.id,j.status,j.artifact_id FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.entity=? AND j.actor=?",(current_run,cell+':'+case['case_id'],args.actor)).fetchall()
                explicit_new_version=bool(case_entry and len(current_execution)==1 and current_execution[0]['status']=='pending' and case_entry.get('execution') and (not Path(case_entry['execution']).name.startswith(str(current_execution[0]['id'])+'-attempt-') or case_entry.get('dependency_repair_reason')))
                if case_entry and len(current_execution)==1 and current_execution[0]['artifact_id']:
                    saved=store.artifact(current_execution[0]['artifact_id'])['payload']
                    from recording_store import stored_attempt_path
                    location=stored_attempt_path(store,current_execution[0]['id'],current_execution[0]['attempts'])
                    explicit_new_version=explicit_new_version or str(location)!=case_entry.get('execution')
                if case_entry and case_entry['status']=='validated' and not explicit_new_version:
                    continue
                if case_entry and case_entry['status']=='validated' and case_entry.get('capture_validated') and case_entry.get('decoder_passed') and not explicit_new_version:
                    continue  # A new explicitly versioned pending job is distinct from replaying this saved capture.
                if case_entry and case_entry.get('definition_file'):
                    from delivery_definitions import resolve
                    case=resolve(case_entry,case)
                # One explicit case at a time preserves comparison anchors and
                # guarantees the first-capture validation gate for every cell.
                if not args.recorded_only:
                    choose_simulation(store,current_run,[cell],[args.actor],[case['case_id']],simulator_inventory=inventories.get(cell),include_baselines=args.include_baselines)
                jobs=store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.entity=? AND j.actor=?",(current_run,cell+':'+case['case_id'],args.actor)).fetchall()
                if len(jobs)!=1:
                    raise ValueError('Missing/ambiguous selected execution')
                if args.recorded_only and jobs[0]['status']!='completed':
                    case_status=jobs[0]['status'];case_error=jobs[0]['error']
                    if case_status=='pending':
                        parent=store.db.execute("SELECT j.status,j.error FROM dependencies d JOIN jobs j ON j.id=d.dependency_id "
                            "WHERE d.job_id=? AND j.stage='construction'",(jobs[0]['id'],)).fetchone()
                        if parent and parent['status'] in ('blocked','failed'):
                            case_status='blocked'
                            case_error='Construction '+parent['status']+': '+str(parent['error'])
                    case_entry.update(status=case_status,error=case_error)
                    refresh()
                    continue
                def inspect_attempt(job_id):
                    finalization_started=None
                    job=store.job(job_id)
                    construction_ids=tuple(r[0]for r in store.db.execute("SELECT j.id FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? AND j.stage='construction'",(job['id'],)))
                    if not args.recorded_only:
                        asyncio.run(run(store,current_run,worker,concurrency=1,per_minute=20,max_attempts=3,
                                        timeout=args.timeout,stage_names=('construction',),job_ids=construction_ids))
                    construction=store.db.execute("SELECT j.status,j.error FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=?",(job['id'],)).fetchone()
                    if construction['status']!='completed':
                        result={'case_id':case['case_id'],'status':'failed','error':'Construction: '+str(construction['error'])}
                    else:
                        job=store.job(job_id)
                        if job['status']=='pending' and not args.recorded_only:
                            execute(store,current_run,args.python,args.host,args.port,args.timeout,job_ids=(job['id'],))
                            job=store.job(job['id'])
                        if job['status']!='completed':
                            result={'case_id':case['case_id'],'status':'failed','error':job['error']}
                            from recording_store import attempt_path
                            failed_attempt=attempt_path(current_run,job['id'],job['attempts'])
                            if failed_attempt.exists():
                                result['execution']=str(failed_attempt)
                                result['static_rejection']=(failed_attempt/'static.stderr.log').exists() and not (failed_attempt/'recorded.stdout.log').exists()
                        else:
                            observed=store.artifact(job['artifact_id'])['payload']
                            from recording_store import stored_attempt_path
                            attempt=stored_attempt_path(store,job['id'],job['attempts'])
                            if args.recorded_only:
                                from batch_pipeline.completion import verify
                                verify(attempt,observed['completion']['binding'])
                            finalization_started=time.time()
                            destination=attempt/'traffic_spec'
                            result={'case_id':case['case_id'],'status':'failed','execution':str(attempt),
                                    'maneuver_completed':observed['maneuver_completed'],'rebuild_required':observed['rebuild_required']}
                            try:
                                if not destination.exists():
                                    command=[sys.executable if args.production else args.python,str(project/'scenario_pipeline/pipeline.py'),'adapt-trace',
                                        '--capture',str(attempt/'capture'),'--original-run',str(attempt),
                                        '--library',str(args.library.resolve()),'--output',str(destination),'--validator',str(args.validator.resolve())]
                                    with (attempt/'adapter.stdout.log').open('w') as out,(attempt/'adapter.stderr.log').open('w') as err:
                                        subprocess.run(command,env=env,stdout=out,stderr=err,check=True,timeout=args.timeout)
                                report=json.loads((destination/'adapter_report.json').read_text())
                                if not report.get('decoder_validation',{}).get('passed'):
                                    raise ValueError('Decoder validation did not pass')
                                result.update(scene_graphs=str(attempt/'capture'),traffic_spec=str(destination),
                                              frames=report['frames'],decoder_passed=True,
                                              verified_videos=observed['video_references'])
                                trace=json.loads((destination/'trace.json').read_text())['scenes']
                                required={'C230289':'speed_limit_sign','C111325':'stop_sign','C111331':'traffic_signal'}.get(cell)
                                config=json.loads((attempt/'config.json').read_text()) if (attempt/'config.json').exists() else {}
                                if cell=='C230289' and config.get('unsigned_context'):
                                    if any(d['kind']=='speed_limit_sign' for scene in trace for d in scene['devices']):
                                        raise ValueError('Unsigned cap context contains a speed-limit sign')
                                    required=None
                                if required:
                                    devices=[d for scene in trace for d in scene['devices'] if d['kind']==required and d.get('governs')]
                                    if not devices:
                                        raise ValueError('Missing physical device/lane governance in trace: '+required)
                                    if required=='speed_limit_sign' and not any('speed_value' in d for d in devices):
                                        raise ValueError('Missing observed speed-limit value')
                                    if required=='traffic_signal' and not all(any(d['kind']==required and d.get('governs') and d.get('indications') for d in scene['devices']) for scene in trace):
                                        raise ValueError('Missing observed governing signal state in a frame')
                                if cell=='C329610' and not all(any(r['kind']==kind for r in trace[0]['structures'])for kind in ('centre_line','intersection','lane')):
                                    raise ValueError('Left-turn trace lacks native divider/intersection/lane geometry')
                                if cell=='C245490' and sum(r['kind']=='lane' for r in trace[0]['structures'])<(1 if case.get('context_variant',{}).get('realized_maneuver')=='straight_travel' else 2):
                                    raise ValueError('Lane-change trace lacks multiple native driving lanes')
                                # The first-case gate validates the capture mechanism.
                                # Target failures remain failures, but do not invalidate
                                # complete original recordings or their native geometry.
                                result['capture_validated']=bool(observed['maneuver_completed'])
                                if observed['rebuild_required']:
                                    if args.production and args.recorded_only and (attempt/'offline_recovery.json').is_file():
                                        from batch_pipeline.carla import verified_closed_video_recovery
                                        result.update(verified_closed_video_recovery(attempt,case,observed))
                                    else:
                                        raise ValueError('Execution has unconfirmed setup or targets')
                                result.update(status='validated')
                            except Exception as exc:
                                result['error']=str(exc)
                            if result.get('decoder_passed'):
                                try:
                                    from review_recordings import report,render
                                    from authored_context import inject,assumptions
                                    cfg=json.loads((attempt/'config.json').read_text()) if (attempt/'config.json').exists() else {}
                                    from expected_labels import scene_context
                                    context=scene_context(case,attempt,legacy=not args.production)
                                    if context:inject(attempt,context,args.validator)
                                    measured=report(case,attempt,production=args.production)
                                    numeric=None if args.production else measured.get('speed_evaluation')
                                    if numeric and numeric.get('expected_speed_rule_label') in ('compliant','non_compliant') and numeric.get('intended_numeric_label') in ('compliant','non_compliant') and numeric['expected_speed_rule_label']!=numeric['intended_numeric_label']:
                                        result.update(status='failed',intended_label_attained=False,error='Intended numeric speed label not achieved across the full delivered trace; preserved diagnostic recording')
                                    elif numeric:
                                        result['intended_label_attained']=numeric.get('expected_speed_rule_label')==numeric.get('intended_numeric_label') and numeric.get('expected_speed_rule_label')!='unknown'
                                    if numeric and not result.get('intended_label_attained',False):
                                        result.update(status='failed',error='Missing evidence or unintended full-trace numeric outcome')
                                    result['measured_review']=str(attempt/'measured_review.json')
                                    from expected_labels import expectation,sha
                                    if case.get('target_type')!='baseline':
                                        if args.production:
                                            from production_verdicts import expectation as production_expectation,validate
                                            expected=validate(production_expectation(case,attempt,measured,context))
                                        else:
                                            expected=expectation(case,attempt,measured,context)
                                        from expected_labels import first_scene
                                        if first_scene(attempt/'traffic_spec/trace.json').get('assumptions',[])!=assumptions(context):
                                            raise ValueError('Delivered Core does not preserve the declared expected-label assumptions')
                                        definition_path=attempt/'accepted_case_definition.json'
                                        atomic(definition_path,case);expected['definition_sha256']=sha(definition_path)
                                        atomic(attempt/'expected_label.json',expected)
                                        result.update(expected_label=expected['expected_label'],expected_label_record=str(attempt/'expected_label.json'),definition_file=str(definition_path),expected_label_status=('evidence_accepted' if expected.get('evidence_status')=='accepted' else 'needs_repair') if args.production else ('judgment_sweep' if expected['judgment_sweep'] else 'accepted' if expected['intention_matched'] else 'needs_repair'))
                                        if (expected.get('evidence_status')!='accepted') if args.production else (not expected['judgment_sweep'] and (not expected['intention_matched'] or expected['missing_evidence'])):
                                            result.update(status='failed',error='Expected scenario outcome not achieved or required applicability evidence missing')
                                    from recording_store import timed_phase
                                    with timed_phase(attempt,'review_render'):
                                        result['event_review']=render(case,attempt,measured)
                                except Exception as exc:
                                    result.update(status='failed',review_error=str(exc),error='Recording review failed: '+str(exc))
                    return result
                from batch_pipeline.repairs import repair_until_accepted,schedule_repair
                result=repair_until_accepted(jobs[0]['id'],inspect_attempt,
                    lambda job_id,failure:schedule_repair(store,current_run,job_id,failure,timeout=args.timeout),max_repairs=0 if args.recorded_only else args.max_repairs)
                if case_entry:
                    if result.get('execution') and case_entry.get('execution')!=result['execution']:
                        history=case_entry.setdefault('superseded_delivery_attempts',[])
                        prior={k:case_entry[k] for k in ('execution','status','error') if k in case_entry}
                        if prior and prior not in history:history.append(prior)
                    case_entry.update(result)
                    if 'error' not in result:case_entry.pop('error',None)
                    if result['status']=='validated':case_entry.pop('dependency_repair_reason',None)
                else:
                    entry['cases'].append(result)
                    case_entry=result
                if case_entry.get('status')=='validated':
                    from delivery_contract import inspect_case
                    from recording_store import accept_recording
                    acceptance_started=time.time()
                    accepted=inspect_case(entry,case_entry)
                    case_entry['recording_id']=accept_recording(case_entry['execution'],accepted)
                    from recording_store import record_phase
                    record_phase(case_entry['execution'],'acceptance',acceptance_started,'accepted')
                refresh()
                print(json.dumps({'cell':cell,'case':case['case_id'],'status':result['status'],'error':result.get('error')}),flush=True)
                key=variant(case)
                if result.get('static_rejection'):
                    continue  # No driving/capture attempt occurred; next feasible probe establishes the gate.
                if key not in capture_gates and not (result.get('capture_validated') and result.get('decoder_passed')):
                    entry.update(status='blocked',error='Capture gate still unresolved after diagnosed repair; independent cases continue')
                    continue
                capture_gates.add(key)
            else:
                expected=selected if args.recorded_only else info['config'].get('explicit_repair_selection',{}).get(cell,[c['case_id'] for c in cases])
                all_attempted=set(expected)<={c['case_id'] for c in entry['cases'] if c['status']!='unselected'}
                selected_entries=[c for c in entry['cases'] if c['status']!='unselected']
                still_pending=not all_attempted or any(c['status'] in ('pending','running') for c in selected_entries)
                blocking_plans=selected_incomplete_plans(data.get('sweep_specs',[]),cases,selected) if args.recorded_only else incomplete
                entry['selected_incomplete_plans']=blocking_plans
                entry['status']='pending' if still_pending else 'validated' if not blocking_plans and selected_entries and all(c['status']=='validated' for c in selected_entries) else 'failed'
                entry.pop('error',None)
            refresh()
        reports=[]
        from batch_pipeline.export import scoped_sweep_reports
        for run_id in {args.run}|{c.get('run_id',args.run) for c in delivery['cells'] if c['cell_id'] in args.cell}:
            if stages.run_info(store,run_id)['config'].get('judgment_completion_policy'):
                reports.extend(scoped_sweep_reports(store,run_id,args.cell,args.actor))
        delivery['sweep_completion_acceptance']=[{'cell_id':s['cell_id'],'sweep_id':s['sweep_id'],'selected_count':s.get('selected',0),'planned_count':s.get('planned',0),**s.get('completion_acceptance',{})} for s in reports]
        failed_sweeps=any(s.get('status')!='passed' for s in delivery['sweep_completion_acceptance'] if not args.recorded_only or s['selected_count']>0)
        delivery['status']='complete' if not failed_sweeps and {c['cell_id'] for c in delivery['cells']} == set(delivery['expected_cells']) and all(c['status']=='validated' for c in delivery['cells']) else 'incomplete'
        refresh()
        requested_complete=bool(args.case and all(any(c['case_id']==ident and c['status']=='validated' and c.get('capture_validated') and c.get('decoder_passed') for e in delivery['cells'] if e['cell_id'] in args.cell for c in e['cases']) for ident in args.case))
        # A per-cell selection may finish before the aggregate campaign. Keep
        # the global status incomplete while returning success for that request.
        return 0 if delivery['status']=='complete' or requested_complete else 1
    finally:
        store.close()


if __name__=='__main__':
    raise SystemExit(main())
