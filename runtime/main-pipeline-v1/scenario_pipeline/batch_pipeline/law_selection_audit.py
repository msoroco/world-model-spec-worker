"""Independent, deterministic acceptance checks for minimum-cell outputs."""
from .store import encode


def verify_solution(report, candidates, requirements, fixed_training=(), retained_heldout=()):
    """Reject a claimed selection without all coverage and separation witnesses.

    This validates a feasible solution independently of the MILP construction.
    Global optimality still requires completed candidate discovery and solver proof.
    """
    errors = []
    selected = {s:set(report.get('selection',{}).get(s,[])) for s in requirements}
    for split in requirements:
        if len(selected[split])!=len(report.get('selection',{}).get(split,[])):
            errors.append('Duplicate selected cells: '+split)
    if not set(fixed_training)<=selected['training']:
        errors.append('Fixed training ownership was dropped')
    retained = set(retained_heldout)-set(fixed_training)
    if not retained<=selected['heldout']:
        errors.append('Compatible held-out ownership was dropped')
    if selected['training'] & selected['testing']:
        errors.append('Training/testing cell overlap')
    if selected['testing'] & selected['heldout']:
        errors.append('Testing/heldout cell overlap')
    shared = selected['training'] & selected['heldout']
    exceptions = report.get('overlap_exceptions',[])
    if shared:
        strict = report.get('strict_separation_proof',{})
        if strict.get('status')!='infeasible' or not strict.get('solver',{}).get('lexicographic_solves') or strict['solver']['lexicographic_solves'][0]['status']!=2:
            errors.append('Overlap lacks a strict infeasibility proof')
        if {e['cell'] for e in exceptions}!=shared:
            errors.append('Overlap exception list does not match selected shared cells')
    elif exceptions:
        errors.append('Spurious overlap exception')
    # Compare the entire candidate payload, not just its law/cell identifiers.
    known = {encode(a) for a in candidates}
    witnesses = {}
    for witness in report.get('witnesses',[]):
        split,target = witness.get('split'),witness.get('requirement')
        base = {k:v for k,v in witness.items() if k not in ('split','requirement')}
        if encode(base) not in known:
            errors.append('Witness does not match a current candidate')
        if split not in requirements or target not in requirements.get(split,[]):
            errors.append('Unexpected coverage witness')
            continue
        if witness.get('cell') not in selected[split] or target not in witness.get('covers',[]) or split not in witness.get('splits',requirements):
            errors.append('Witness does not support the selected assignment')
        if (split,target) in witnesses:
            errors.append('Duplicate requirement witness')
        witnesses[split,target] = witness
    for split,targets in requirements.items():
        for target in targets:
            if (split,target) not in witnesses:
                errors.append('Uncovered requirement: '+split+'/'+target)
    for cell in shared:
        train_laws = {v['law'] for (s,t),v in witnesses.items() if s=='training' and v['cell']==cell}
        held_laws = {v['law'] for (s,t),v in witnesses.items() if s=='heldout' and v['cell']==cell}
        if train_laws & held_laws:
            errors.append('Shared cell targets the same law in training and heldout')
    expected_totals = {s:len(v) for s,v in selected.items()}
    if report.get('total_cells')!=expected_totals:
        errors.append('Reported total cell counts disagree with selections')
    additional = {'training':len(selected['training']-set(fixed_training)),
                  'testing':len(selected['testing']),
                  'heldout':len(selected['heldout']-set(retained_heldout))}
    if report.get('additional_cells')!=additional:
        errors.append('Reported additional cell counts disagree with selections')
    trace = report.get('solver',{}).get('lexicographic_solves',[])
    if report.get('exact_minimum_proven') and (not trace or any(v['status']!=0 for v in trace)):
        errors.append('Exact-minimum claim lacks optimal solver termination for every objective')
    return {'passed':not errors,'errors':errors,'requirements_checked':sum(map(len,requirements.values())),
            'witnesses_checked':len(witnesses),'total_cells_checked':expected_totals}
