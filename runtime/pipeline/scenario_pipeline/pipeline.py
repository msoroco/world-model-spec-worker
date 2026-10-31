#!/usr/bin/env python3
"""CLI for the autonomous local scenario pipeline (Python 3.11+)."""
import argparse
import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from workspaces import campaign_path
from pipeline_paths import CATALOG_DIR, SHARED_INPUTS_DIR, STATE_PATH, RUNS_ROOT, require_artifact_path, initialize_inputs
from batch_pipeline import stages
from batch_pipeline.store import Store, digest, encode
from batch_pipeline.runner import run, materialize_cached
from batch_pipeline.export import export
from batch_pipeline.carla import execute

ROOT = Path(__file__).resolve().parent


def import_catalog(store, path):
    from catalog import validate_catalog
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    validate_catalog(value)
    ident = hashlib.sha256(raw).hexdigest()
    with store.transaction():
        store.db.execute('INSERT OR IGNORE INTO catalogs VALUES(?,?,?)',(ident,str(Path(path).resolve()),encode(value)))
        for c in value['cells']:
            store.db.execute('INSERT OR IGNORE INTO cells VALUES(?,?,?,?,?,?,?,?)',
                (ident,c['cell_id'],c['layout'],c['maneuver'],c['control'],c['grounding'],c.get('actor_status'),encode(c)))
    return ident


def cell_provenance(source, cell):
    laws = set(cell.get('source_laws', [])) | set(cell.get('cooccurrence_laws', []))
    for axis,field in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]:
        for term in source[axis]:
            if term['id']==cell[field]:
                laws.update(term.get('source_laws', []))
    result = []
    for key in sorted(laws):
        annotation = source.get('law_analysis', {}).get(key)
        result.append({'law_id':key,'annotation_version':digest(annotation) if annotation else None,
                       'review_status':annotation.get('review_status','unknown') if annotation else 'unknown'})
    return {'annotations':result,'cell_version':digest(cell)}


def select(store, run_id, cell_ids=(), actor_ids=(), limit=20):
    if limit < 0:
        raise ValueError('Selection limit cannot be negative')
    source = stages.catalog(store,run_id)
    selected = [c for c in source['cells'] if not cell_ids or c['cell_id'] in cell_ids]
    if cell_ids and set(cell_ids)-{c['cell_id'] for c in selected}:
        raise ValueError('Unknown selected cell IDs')
    count = 0
    # Prefer grounded cells unless explicit IDs were requested.
    selected.sort(key=lambda c:(c['grounding']!='grounded',c['cell_id']))
    with store.transaction():
        for c in selected:
            actors = [a for a in stages.actors(c) if not actor_ids or a in actor_ids]
            if not actors:
                continue
            if limit and count>=limit:
                break
            for actor in actors:
                config=stages.run_info(store,run_id)['config']
                payload={'cell':c,'actor':actor,'catalog_provenance':cell_provenance(source,c),
                    'explicit_contexts': config.get('explicit_contexts', []),
                    'context_predicates': config.get('context_predicates', {})}
                laws=sorted(config.get('law_scope', {}).get('records', source['law_records']))
                config=stages.run_info(store,run_id)['config']
                size=config.get('law_batch_size',40)
                deps=[]
                for index in range(0,len(laws),size):
                    subset=laws[index:index+size]
                    deps.append(stages.enqueue(store,run_id,'relevance_batch',c['cell_id']+':batch:'+str(index//size),actor,
                        dict(payload,law_ids=subset,law_versions={k:digest(source['law_records'][k]) for k in subset},
                             summary_versions={k:digest(config.get('summaries',{}).get(k)) for k in subset})))
                stages.enqueue(store,run_id,'relevance',c['cell_id'],actor,payload,deps)
            count += 1
    materialize_cached(store,run_id)
    return count


def create_run(store, ident, catalog_id, output, summaries, worker, model, law_batch_size=40, simulator_context=None, context_ids=(), context_registry=None, laws=None, fewshots=None):
    if store.db.execute('SELECT 1 FROM runs WHERE id=?',(ident,)).fetchone():
        raise ValueError('Run already exists; use select/resume: '+ident)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', ident):
        raise ValueError('Run ID must be a simple name, not a path')
    records = {}
    if summaries:
        for line in Path(summaries).read_text().splitlines():
            v = json.loads(line)
            if v['id'] in records:
                raise ValueError('Duplicate summary ID')
            records[v['id']] = v
    context_path = Path(context_registry) if context_registry else SHARED_INPUTS_DIR/'context_predicates_draft.json'
    if not context_path.exists() and not context_registry:
        context_path=ROOT/'data/bootstrap/context_predicates_draft.json'
    predicates = json.loads(context_path.read_text()) if context_path.exists() else {}
    unknown = set(context_ids)-set(predicates)
    if unknown:
        raise ValueError('Unknown explicit context overlays: '+', '.join(sorted(unknown)))
    resources = json.loads(Path(simulator_context).read_text()) if simulator_context else None
    readme = ROOT.parent/'README.md'
    if resources is None and readme.exists() and 'carla' in readme.read_text().lower():
        text = readme.read_text()
        resources = {'project_root': str(ROOT.parent), 'installation_readme': {'path': str(readme), 'text': text, 'version': digest(text)},
                     'resource_paths': [str(p) for p in (ROOT.parent/'carla', ROOT.parent/'envs', ROOT.parent/'scripts') if p.exists()],
                     'policy': 'Survey these documented local resources; no server launch, driving run, or structured scene-graph extraction during construction.'}
    if resources is not None and not isinstance(resources, dict):
        raise ValueError('Simulator context must be a JSON object')
    config = {'judgment_policy': 'fixed_sweeps', 'context_predicates': predicates, 'explicit_contexts': sorted(set(context_ids)), 'simulator_context': resources, 'law_batch_size':law_batch_size,'summaries':records,'summary_source':str(Path(summaries).resolve()) if summaries else None,
              'summary_version':digest(records),'model':{'identity':model,'worker_argv':worker}}
    from batch_pipeline.run_inputs import freeze_inputs
    config.update(freeze_inputs(store, catalog_id, laws, fewshots, output))
    from batch_pipeline.runtime_dependencies import coordinated_access,discover,snapshot
    with coordinated_access():
        config['runtime_dependencies']=snapshot(discover(resources))
    store.db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(ident,catalog_id,str(Path(output).resolve()),encode(config),time.time()))
    from batch_pipeline.store import atomic
    atomic(Path(output)/'runtime_dependencies.json',config['runtime_dependencies'])
    return ident


def seed_library(store, path):
    value = json.loads(Path(path).read_text())
    with store.transaction():
        for t in value['templates']:
            if t['template_id']!=t['law_id']+'@'+t['actor']:
                raise ValueError('Invalid shared template identity')
            store.merge_template(t)
    return len(value['templates'])


def choose_simulation(store, run_id, cell_ids=(), actor_ids=(), case_ids=(), limit=None,
                      simulation_budget_per_sweep=3, sweep_ids=(), simulator_inventory=None, include_baselines=False, expected_partition=None):
    if limit is not None and limit < 1 or simulation_budget_per_sweep < 1:
        raise ValueError('Simulation selection requires positive bounded budgets')
    info=stages.run_info(store, run_id)
    expected_partition=expected_partition or info['config'].get('scenario_partition')
    policy_root=Path(store.path).resolve().parent.parent
    from law_split import active_manifest, assignment_allowed
    partition_policy=active_manifest(policy_root)
    count = 0
    rows = store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='cases' AND j.status='completed' ORDER BY j.id", (run_id,)).fetchall()
    matched_cases, matched_sweeps = set(), set()
    with store.transaction():
        for row in rows:
            job = dict(row)
            if cell_ids and job['entity'] not in cell_ids or actor_ids and job['actor'] not in actor_ids:
                continue
            request = json.loads(job['payload'])
            artifact = store.artifact(job['artifact_id'])
            if any(digest(store.get_template(k)) != version for k, version in artifact['provenance'].get('template_versions', {}).items()):
                continue
            result = artifact['payload']
            selected_ids = set(case_ids)
            if not case_ids:
                for spec in result.get('sweep_specs', []):
                    if spec['status'] == 'complete' and (not sweep_ids or spec['sweep_id'] in sweep_ids):
                        matched_sweeps.add(spec['sweep_id'])
                        selected_ids.update(spec['selection_order'][:simulation_budget_per_sweep])
            for case in result['cases']:
                if case['target_type']=='baseline' and not include_baselines:
                    if case['case_id'] in case_ids:
                        raise ValueError('Baseline simulation requires include_baselines=True or --include-baselines')
                    continue
                if case['case_id'] not in selected_ids:
                    continue
                if partition_policy and case.get('target_law_id'):
                    roles=(expected_partition,) if expected_partition else ('training','testing','heldout')
                    if not any(assignment_allowed(case['target_law_id'],job['entity'],job['actor'],role,policy_root) for role in roles):
                        raise ValueError('Case is outside reviewed law/cell/actor partition: '+case['case_id'])
                matched_cases.add(case['case_id'])
                if limit is not None and count >= limit:
                    continue
                existing = store.db.execute("SELECT j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.entity=? AND j.actor=?", (run_id, job['entity']+':'+case['case_id'], job['actor'])).fetchall()
                if any(json.loads(r['payload']).get('case') == case and json.loads(r['payload']).get('input_revision') == request.get('input_revision') for r in existing):
                    continue  # Frozen selections count even when attempts fail; no gap filling.
                payload = dict(request, case=case)
                if simulator_inventory is not None:
                    payload['simulator_inventory']=simulator_inventory
                construction = stages.enqueue(store,run_id,'construction',job['entity']+':'+case['case_id'],job['actor'],payload,[job['id']])
                stages.enqueue(store,run_id,'execution',job['entity']+':'+case['case_id'],job['actor'],payload,[construction])
                count += 1
        if set(case_ids)-matched_cases or set(sweep_ids)-matched_sweeps and not case_ids:
            raise ValueError('Unknown or stale selected cases/sweeps')
    return count


def main(argv=None):
    import sys
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == 'law-plan':
        from batch_pipeline.law_planning import main as planning_main
        return planning_main(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=STATE_PATH)
    sub = parser.add_subparsers(dest='command',required=True)
    planning_parser = sub.add_parser('law-plan',help='Versioned exhaustive relevance mapping and minimum-cell partition planning')
    planning_parser.add_argument('planning_args',nargs=argparse.REMAINDER)
    sub.add_parser('init-inputs',help='Copy read-only bootstrap inputs to the central artifact root without overwriting existing inputs')
    p = sub.add_parser('import',help='Import an existing JSON catalog unchanged and start a run')
    p.add_argument('--catalog',type=Path,required=True);p.add_argument('--run',required=True)
    p.add_argument('--summaries',type=Path);p.add_argument('--templates',type=Path)
    p.add_argument('--laws',type=Path,help='Restrict processing to these exact catalog laws (JSONL)')
    p.add_argument('--fewshots',type=Path,help='Snapshot indexed downstream examples for cases and construction')
    p.add_argument('--context',action='append',default=[],help='Explicitly attach a named context to this run; base triple stays unchanged');p.add_argument('--context-registry',type=Path);p.add_argument('--simulator-context',type=Path,help='JSON describing available CARLA/map resources; needed only for selected construction');p.add_argument('--output',type=Path);p.add_argument('--worker',help='JSON argv array for the model bridge')
    p.add_argument('--model',default='unspecified');p.add_argument('--law-batch-size',type=int,default=40)
    for name in ('select','select-simulation'):
        p = sub.add_parser(name);p.add_argument('--run',required=True)
        p.add_argument('--cell',action='append',default=[]);p.add_argument('--actor',action='append',default=[])
        p.add_argument('--limit',type=int,default=20 if name=='select' else None)
        if name=='select-simulation':
            p.add_argument('--partition',choices=('training','testing','heldout'),help='Enforce active law-specific scenario eligibility')
            p.add_argument('--case',action='append',default=[])
            p.add_argument('--sweep',action='append',default=[])
            p.add_argument('--simulation-budget-per-sweep',type=int,default=3)
            p.add_argument('--include-baselines',action='store_true',help='Permit explicit simulation of neutral baseline definitions')
    for name in ('run','resume'):
        p = sub.add_parser(name);p.add_argument('--run',required=True)
        p.add_argument('--worker',help='JSON argv array; overrides stored model bridge')
        p.add_argument('--concurrency',type=int,default=4);p.add_argument('--requests-per-minute',type=float,default=30)
        p.add_argument('--max-attempts',type=int,default=3);p.add_argument('--timeout',type=int,default=300)
        p.add_argument('--stage',action='append',choices=stages.SEMANTIC_STAGES)
        p.add_argument('--retry-failed',action='store_true')
    for name in ('status','report'):
        p = sub.add_parser(name);p.add_argument('--run',required=True)
    p = sub.add_parser('simulate');p.add_argument('--run',required=True);p.add_argument('--max-repairs',type=int,default=2)
    p.add_argument('--python');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=20000);p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--engines',type=Path,help='JSON array of dedicated local/SSH CARLA engines')
    p = sub.add_parser('adapt-trace', help='Convert raw recorded scene graphs to TrafficSpec runtime JSON')
    p.add_argument('--capture', type=Path, required=True);p.add_argument('--original-run', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True);p.add_argument('--output', type=Path, required=True)
    p.add_argument('--validator', type=Path, help='Full-Core decoder validator executable')
    p=sub.add_parser('migrate-law-split',help='Stage/apply the approved law-specific partition migration without native execution')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply',action='store_true')
    p.add_argument('--policy',type=Path)
    sub.add_parser('refresh-workspaces',help='Refresh derived workspace navigation without copying implementation')
    p = sub.add_parser('organize-work',help='Copy implementation work into category/cell/law workspaces')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply',action='store_true')
    sub.add_parser('organize-sets',help='Index five active sets from precomputed splits, preserving historical sets')
    p = sub.add_parser('finalize-set',help='Verify and finalize a frozen selection without copying evidence')
    p.add_argument('--set',required=True,dest='set_id')
    p = sub.add_parser('package-set',help='Materialize a finalized set only when a portable copy is requested')
    p.add_argument('--set',required=True,dest='set_id');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--zip',action='store_true',dest='archive')
    p = sub.add_parser('runtime-edit',help='Coordinate an intentional implementation edit and rerun affected cases within the existing run')
    p.add_argument('--run',required=True);p.add_argument('--reason',required=True);p.add_argument('--case',action='append',default=[])
    p.add_argument('--edit-command',help='JSON argv array, run under the exclusive runtime lock')
    p.add_argument('--python',required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=20000);p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--library',type=Path,required=True);p.add_argument('--validator',type=Path,required=True)
    p = sub.add_parser('review');p.add_argument('--artifact',required=True);p.add_argument('--status',choices=('unreviewed','approved','rejected'),required=True)
    args = parser.parse_args(argv)
    if args.command == 'law-plan':
        from batch_pipeline.law_planning import main as planning_main
        return planning_main(args.planning_args)
    if args.command == "init-inputs":
        print(json.dumps(initialize_inputs(), indent=2))
        return 0
    if args.command == 'adapt-trace':
        from traffic_spec_adapter.adapter import convert
        from recording_store import timed_phase
        from contextlib import nullcontext
        destination = require_artifact_path(args.output)
        tracked=(Path(args.original_run).parent/'metadata.json').is_file()
        with timed_phase(args.original_run,'conversion') if tracked else nullcontext():
            report = convert(args.capture, args.original_run, args.library, destination)
        if args.validator:
            from traffic_spec_adapter.validate import validate_output
            with timed_phase(args.original_run,'core_decode') if tracked else nullcontext():
                report = validate_output(destination, args.validator)
        print(json.dumps({'output':str(destination),'frames':report['frames'],
                          'decoder_validation':report['decoder_validation']}, indent=2))
        return 0
    if args.command == 'migrate-law-split':
        from migrate_law_split import migrate, DEFAULT_POLICY
        print(json.dumps(migrate(policy_path=args.policy or DEFAULT_POLICY,apply=args.apply),indent=2));return 0
    if args.command == 'refresh-workspaces':
        from organize_work import refresh_workspaces
        print(json.dumps(refresh_workspaces(),indent=2));return 0
    if args.command == 'organize-work':
        from organize_work import organize_work
        print(json.dumps(organize_work(apply=args.apply),indent=2));return 0
    if args.command == 'organize-sets':
        from organize_sets import organize_sets
        print(json.dumps(organize_sets(),indent=2));return 0
    if args.command in ('finalize-set','package-set'):
        from recording_store import finalize_set, package_set
        result=finalize_set(args.set_id) if args.command=='finalize-set' else package_set(args.set_id,args.output,args.archive)
        print(json.dumps(result,indent=2));return 0
    args.db = require_artifact_path(args.db)
    if args.command == "import" and args.output:
        args.output = require_artifact_path(args.output)
    store = Store(args.db)
    try:
        if args.command == 'import':
            if args.law_batch_size<1:
                raise ValueError('Law batch size must be positive')
            cid = import_catalog(store,args.catalog)
            worker = json.loads(args.worker) if args.worker else []
            if not isinstance(worker,list) or not all(isinstance(v,str) for v in worker):
                raise ValueError('Worker must be a JSON argv array')
            create_run(store,args.run,cid,args.output or campaign_path(args.run,RUNS_ROOT),args.summaries,worker,args.model,args.law_batch_size,args.simulator_context,args.context,args.context_registry,args.laws,args.fewshots)
            if args.templates:seed_library(store,args.templates)
            print(json.dumps({'run_id':args.run,'catalog_id':cid,'cells':store.db.execute('SELECT COUNT(*) FROM cells WHERE catalog_id=?',(cid,)).fetchone()[0]}))
        elif args.command == 'select':
            print('Selected cells:',select(store,args.run,args.cell,args.actor,args.limit))
        elif args.command == 'select-simulation':
            print('Selected cases:',choose_simulation(store,args.run,args.cell,args.actor,args.case,args.limit,args.simulation_budget_per_sweep,args.sweep,include_baselines=args.include_baselines,expected_partition=args.partition))
        elif args.command in ('run','resume'):
            if args.concurrency<1 or args.max_attempts<1 or args.requests_per_minute<0 or args.timeout<1:
                raise ValueError('Invalid concurrency, retry or rate-limit setting')
            if args.retry_failed:
                store.db.execute("UPDATE jobs SET status='pending',available=0,error=NULL WHERE id IN (SELECT job_id FROM run_jobs WHERE run_id=? AND active=1) AND stage!='execution' AND status IN ('failed','blocked')",(args.run,))
            materialize_cached(store,args.run)
            configured=stages.run_info(store,args.run)['config']['model']['worker_argv']
            command = json.loads(args.worker) if args.worker else configured
            if command != configured:
                raise ValueError('Changing the model bridge requires a new run configured before selection; cached work must not change backend silently.')
            if not isinstance(command,list) or not all(isinstance(s,str) for s in command):
                raise ValueError('Worker must be a JSON argv array')
            asyncio.run(run(store,args.run,command,args.concurrency,args.requests_per_minute,args.max_attempts,args.timeout,args.stage))
        elif args.command == 'runtime-edit':
            import subprocess
            from batch_pipeline.runtime_dependencies import coordinated_access,refresh
            with coordinated_access(editing=True):
                if args.edit_command:
                    command=json.loads(args.edit_command)
                    if not isinstance(command,list) or not command or not all(isinstance(v,str) for v in command):raise ValueError('Edit command must be a nonempty JSON argv array')
                    completed=subprocess.run(command,check=False)
                    if completed.returncode:print('Case repairs remain unresolved for',cell)
                affected=refresh(store,args.run,args.reason,args.case)
            if affected:
                from batch_pipeline.repairs import execute_with_repairs
                print('Recorded repaired executions:',execute_with_repairs(store,args.run,args.python,args.host,args.port,args.timeout,max_repairs=getattr(args,'max_repairs',2)))
                selection={}
                for ident in affected:
                    request=json.loads(store.job(ident)['payload']);selection.setdefault(request['cell']['cell_id'],[]).append(request['case']['case_id'])
                for cell,cases in selection.items():
                    command=[__import__('sys').executable,str(ROOT/'run_selected.py'),'--db',str(args.db),'--run',args.run,'--cell',cell,'--python',args.python,'--host',args.host,'--port',str(args.port),'--timeout',str(args.timeout),'--library',str(args.library),'--validator',str(args.validator)]
                    for case in cases:command+=['--case',case]
                    completed=subprocess.run(command,check=False)
                    if completed.returncode:print('Case repairs remain unresolved for',cell)
        elif args.command == 'simulate':
            if args.timeout<1:
                raise ValueError('Execution timeout must be positive')
            if not args.engines and not args.python:
                raise ValueError('Specify --engines or --python for a single engine')
            engines = json.loads(args.engines.read_text()) if args.engines else None
            from batch_pipeline.repairs import execute_with_repairs
            print('Accepted recorded executions:',execute_with_repairs(store,args.run,args.python,args.host,args.port,args.timeout,max_repairs=getattr(args,'max_repairs',2),engines=engines))
        elif args.command == 'review':
            updated = store.db.execute('UPDATE artifacts SET review_status=?,reviewed_at=? WHERE id=?',
                            (args.status,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),args.artifact))
            if not updated.rowcount:
                raise ValueError('Unknown artifact')
            return 0
        if args.command=='report':
            progress=export(store,args.run)
            print(json.dumps({k:v for k,v in progress.items() if k not in ('jobs','attempts')},indent=2))
            return 0
        counts={}
        for stage,status,count in store.db.execute('SELECT j.stage,j.status,COUNT(*) FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 GROUP BY j.stage,j.status',(args.run,)):
            counts.setdefault(stage,{})[status]=count
        if args.command=='status':
            print(json.dumps({'run_id':args.run,'stage_counts':counts},indent=2))
        if args.command in ('run','resume','simulate','runtime-edit'):
            return int(any(states.get('failed',0) or states.get('blocked',0) for states in counts.values()))
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
