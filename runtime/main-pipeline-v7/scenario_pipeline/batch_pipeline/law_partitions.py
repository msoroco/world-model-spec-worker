"""Exact cell set cover with explicit bounds and strict split separation."""
import json
import platform
from pathlib import Path
from .store import atomic
from .law_planning import sha


def solve(candidates, requirements, fixed_training=(), retained_heldout=(), timeout=30, allow_overlap=False):
    import numpy as np
    import scipy
    from scipy.optimize._highspy._core import _Highs
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import coo_matrix
    splits = ('training','testing','heldout')
    fixed = set(fixed_training)
    cells = sorted({a['cell'] for a in candidates} | fixed | set(retained_heldout))
    index = {(c,s):i for i,(c,s) in enumerate((c,s) for c in cells for s in splits)}
    n = len(index)
    overlap = {c:n+i for i,c in enumerate(cells)} if allow_overlap else {}
    n += len(overlap)
    rows,lo,hi = [],[],[]
    def constraint(coefficients, lower, upper):
        rows.append(coefficients);lo.append(lower);hi.append(upper)
    blockers = []
    witnesses = {}
    candidate_index = {}
    for a in candidates:
        for s in a.get('splits',splits):
            for target in a.get('covers',[]):
                candidate_index.setdefault((s,target),[]).append(a)
    for s, targets in requirements.items():
        for target in targets:
            eligible = candidate_index.get((s,target),[])
            if not eligible:blockers.append({'split':s,'requirement':target})
            witnesses[s,target] = eligible
            constraint({index[c,s]:1 for c in {a['cell'] for a in eligible}},1,np.inf)
    if blockers:return {'status':'blocked','blocking_requirements':blockers,'exact_minimum_proven':False}
    for c in cells:
        t,e,h = (index[c,s] for s in splits)
        constraint({t:1,e:1},-np.inf,1)
        constraint({e:1,h:1},-np.inf,1)
        if allow_overlap:
            # z == training AND heldout.
            z = overlap[c]
            constraint({t:1,h:1,z:-1},-np.inf,1)
            constraint({z:1,t:-1},-np.inf,0)
            constraint({z:1,h:-1},-np.inf,0)
            # Sharing may only target DIFFERENT laws. A same-law shared cell
            # is excluded as a witness in one split by explicit witness vars.
        else:constraint({t:1,h:1},-np.inf,1)
        if c in fixed:constraint({t:1},1,1)
    # Preserve compatible heldout selections. Fixed training takes precedence.
    for c in set(retained_heldout)-fixed:constraint({index[c,'heldout']:1},1,1)
    if allow_overlap:
        # Assignment variables allow a shared cell to witness different laws,
        # rather than banning it simply because both are potentially relevant.
        witness_vars = {}
        for (s,target),eligible in witnesses.items():
            for c in sorted({a['cell'] for a in eligible}):
                witness_vars[c,s,target] = n;n+=1
        for (c,s,target),j in witness_vars.items():
            constraint({j:1,index[c,s]:-1},-np.inf,0)
        for s,targets in requirements.items():
            for target in targets:
                constraint({j:1 for (c,sp,t),j in witness_vars.items() if sp==s and t==target},1,np.inf)
        for c in cells:
            common = set(requirements['training']) & set(requirements['heldout'])
            for target in common:
                a = witness_vars.get((c,'training',target));b = witness_vars.get((c,'heldout',target))
                if a is not None and b is not None:constraint({a:1,b:1},-np.inf,1)
    def matrix():
        rr=[];cc=[];vv=[]
        for i,row in enumerate(rows):
            for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
        return coo_matrix((vv,(rr,cc)),shape=(len(rows),n)).tocsc()
    objectives = []
    if overlap:objectives.append(('overlap_exceptions',{j:1 for j in overlap.values()}))
    objectives.append(('additional_training_testing',{index[c,s]:1 for c in cells for s in ('training','testing') if s!='training' or c not in fixed}))
    objectives.append(('additional_heldout',{index[c,'heldout']:1 for c in cells if c not in retained_heldout}))
    readiness = dict.fromkeys(index,0)
    for a in candidates:
        for s in a.get('splits',splits):
            readiness[a['cell'],s] = max(readiness[a['cell'],s],a.get('readiness_score',0))
    objectives.append(('evidence_readiness',{j:-readiness[c,s] for (c,s),j in index.items()}))
    # Stable rank preference; equal rank sums can retain multiple optima.
    ranks = {c:i+1 for i,c in enumerate(cells)}
    objectives.append(('cell_id_order',{j:ranks[c] for (c,s),j in index.items()}))
    trace=[]; result=None
    for name, coefficients in objectives:
        objective=np.zeros(n)
        for j,v in coefficients.items():objective[j]=v
        result=milp(objective,integrality=np.ones(n),bounds=Bounds(0,1),constraints=LinearConstraint(matrix(),lo,hi),options={'time_limit':timeout,'mip_rel_gap':0})
        trace.append({'objective':name,'status':int(result.status),'message':result.message,
            'upper_bound':None if result.fun is None else float(result.fun),
            'lower_bound':None if getattr(result,'mip_dual_bound',None) is None else float(result.mip_dual_bound),
            'gap':None if getattr(result,'mip_gap',None) is None else float(result.mip_gap)})
        if result.status!=0:break
        optimum=round(result.fun)
        constraint(coefficients,optimum,optimum)
    selection = {s:sorted(c for c in cells if result.x is not None and result.x[index[c,s]]>.5) for s in splits}
    selected_witnesses=[]
    if result.x is not None:
        for (s,target),eligible in witnesses.items():
            options=[a for a in eligible if a['cell'] in selection[s]]
            if allow_overlap:options=[a for a in options if result.x[witness_vars[a['cell'],s,target]]>.5]
            if options:selected_witnesses.append(dict(sorted(options,key=lambda a:(-a.get('readiness_score',0),a['cell'],a['actor']))[0],split=s,requirement=target))
    return {'status':'optimal' if result.status==0 else 'infeasible' if result.status==2 else 'bounded_or_unresolved',
        'exact_minimum_proven':result.status==0,'selection':selection,'witnesses':selected_witnesses,
        'overlap_exceptions':[{'cell':c,'training_laws':[a['law'] for a in selected_witnesses if a['cell']==c and a['split']=='training'],
                               'heldout_laws':[a['law'] for a in selected_witnesses if a['cell']==c and a['split']=='heldout']}
                              for c in set(selection['training']) & set(selection['heldout'])],
        'total_cells':{s:len(v) for s,v in selection.items()},
        'additional_cells':{'training':len(set(selection['training'])-fixed),'testing':len(selection['testing']),
                            'heldout':len(set(selection['heldout'])-set(retained_heldout))},
        'solver':{'scipy':scipy.__version__,'python':platform.python_version(),'backend':'SciPy bundled HiGHS','highs':_Highs().version(),'lexicographic_solves':trace,'time_limit_per_objective_s':timeout},
        'stable_order_policy':'sorted cell IDs and minimum rank sum; equal rank sums may leave multiple optima'}


def optimize_package(planner, candidate_path=None, timeout=30):
    status = planner.report()
    splits = json.loads((planner.root/'inputs/splits.json').read_text())
    ownership = json.loads((planner.root/'ownership-audit.json').read_text())
    summaries = planner.summaries()
    demo_requirements = planner.demo_requirements()
    requirements = {'training':splits['train']+sorted(demo_requirements),'testing':splits['train'],'heldout':splits['test']}
    atomic(planner.root/'coverage-requirements.json',{'requirements':requirements,'demo_gap_tags':demo_requirements})
    relevance = []
    for r in planner.db.execute("SELECT * FROM decisions WHERE decision IN ('relevant','conditional')"):
        v=json.loads(r['payload'])
        relevance.append({'cell':r['cell'],'actor':r['actor'],'law':r['law'],'covers':[r['law']],
            'receipt':r['receipt'],'required_context':v['required_context'],'readiness_score':0})
    # Feasibility is a separate exhaustive decision layer. A partial set of
    # supported proposals cannot prove a global minimum: an unreviewed cell
    # might support a smaller cover. Exclude stale proposals after recall repair.
    current = {(r['cell'],r['actor'],r['law']):r['payload'] for r in planner.db.execute(
        "SELECT cell,actor,law,payload FROM decisions WHERE decision IN ('relevant','conditional')")}
    qualified = []
    accounted = set()
    stale_batches = []
    for row in planner.db.execute("SELECT j.key,j.payload,j.result,r.input_hash,r.result_hash,r.expected,r.completed FROM jobs j LEFT JOIN receipts r ON r.key=j.key WHERE j.stage='evidence' AND j.status='completed' ORDER BY j.key"):
        request = json.loads(row['payload'])
        result = json.loads(row['result'])
        if request.get('fixed_fact_contract')!=planner.fixed_fact_contract(request.get('cells') or [request['cell']]) or request.get('context_refs',[])!=planner.context_refs(request.get('laws',[])):
            stale_batches.append(row['key'])
            continue
        if row['input_hash']!=sha(request) or row['result_hash']!=sha(result) or row['expected']!=row['completed'] or row['completed']!=len(request['positives']):
            stale_batches.append(row['key'])
            continue
        if any(current.get((request['cell'],v['actor'],v['law_id']))!=json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False) for v in request['positives']):
            stale_batches.append(row['key'])
            continue
        for a in result['assignments']:
            accounted.add((a['cell'],a['actor'],a['law']))
            a = dict(a, receipt=row['key'])
            if a['readiness']=='supported':qualified.append(a)
            relevance.append(a)
    evidence_accounting = {'expected_positive_assignments':len(current),
        'completed_current_assignments':len(accounted),
        'unevaluated_assignments':len(set(current)-accounted),'stale_batches':stale_batches}
    evidence_blockers = []
    if set(current)-accounted:
        evidence_blockers.append('Recording feasibility review is incomplete')
    if stale_batches:
        evidence_blockers.append('Stale recording proposals require regeneration')
    if candidate_path:
        raise ValueError('External candidate files are not trusted evidence; use planning evidence receipts')
    reports = {}
    for name, candidates in [('relevance_only',relevance),('feasibility_qualified',qualified)]:
        present = {s:{t for a in candidates if s in a.get('splits',requirements) for t in a['covers']} for s in requirements}
        missing = [{'split':s,'requirement':t} for s,targets in requirements.items() for t in targets if t not in present[s]]
        if missing:
            reports[name]={'status':'blocked','blocking_requirements':missing,'exact_minimum_proven':False}
            continue
        report=solve(candidates,requirements,ownership['fixed_training'],ownership['retained_heldout_candidates'],timeout)
        if report['status']=='infeasible':
            strict=report
            report=solve(candidates,requirements,ownership['fixed_training'],ownership['retained_heldout_candidates'],timeout,True)
            report['strict_separation_proof']=strict
        from .law_selection_audit import verify_solution
        if report.get('selection') and any(report['selection'].values()):
            verification = verify_solution(report,candidates,requirements,ownership['fixed_training'],ownership['retained_heldout_candidates'])
        else:
            verification = {'passed':False,'errors':['No feasible selection returned']}
        report['selection_verification'] = verification
        report['candidate_discovery_blockers'] = status['blockers']+evidence_blockers
        report['exact_minimum_proven'] &= not report['candidate_discovery_blockers'] and verification['passed']
        report['solver_source_sha256'] = sha(Path(__file__).read_bytes())
        report['scope']='current verified candidate universe; global proof requires exhaustive accounting and recall acceptance'
        report['input_hash']=sha([candidates,requirements,ownership])
        reports[name]=report
    reports['mapping_blockers']=status['blockers']
    reports['evidence_accounting']=evidence_accounting
    reports['evidence_blockers']=evidence_blockers
    atomic(planner.root/'solver-implementation.json',{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes()),'source':Path(__file__).read_text()})
    worklist = []
    for kind,report in reports.items():
        if not isinstance(report,dict):continue
        for witness in report.get('witnesses',[]):
            if witness['split']=='training' and witness['requirement'].startswith('demo:'):
                worklist.append(dict(witness,tag='training_demo_gap',solution=kind))
    atomic(planner.root/'training-demo-gap-worklist.json',worklist)
    atomic(planner.root/'partitions.json',reports)
    return reports
