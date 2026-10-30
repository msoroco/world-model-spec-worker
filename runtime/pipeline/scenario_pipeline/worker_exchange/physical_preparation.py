"""Evidence-backed physical completion and capture lifecycle proof gate."""
from .common import read,sha,within

def validate(repo,folder,entry):
    spec=entry.get('physical_preparation',{});path=within(folder,spec['receipt']);proof=read(path)
    if sha(path)!=spec.get('sha256') or proof.get('construction_sha256')!=entry['construction_sha256']:raise ValueError('Stale physical preparation proof')
    fixtures=proof.get('fixtures',[])
    if {f.get('kind') for f in fixtures}!={'complete_motion','incomplete_motion','missing_evidence'}:raise ValueError('Three physical outcome fixtures required')
    for f in fixtures:
        if f.get('exit_code')!=0 or not f.get('command') or sha(within(folder,f['log']))!=f.get('log_sha256'):raise ValueError('Missing physical fixture test')
        result=read(within(folder,f['result']))
        if sha(within(folder,f['result']))!=f.get('result_sha256'):raise ValueError('Changed physical fixture result')
        expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[f['kind']]
        check=result.get('physical_checks',{}).get('maneuver',{})
        if check.get('status')!=expected or not check.get('method') or not check.get('sources'):raise ValueError('Physical completion lacks measured evidence')
        if result.get('maneuver_completed')!=(expected=='met'):raise ValueError('Completion boolean differs from evidence status')
        if expected=='met' and (not result.get('realized_observables') or result.get('provenance_kind')!='native'):raise ValueError('Complete fixture lacks realized Native observations')
    life=proof.get('lifecycle',{})
    if life.get('events')!=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started'] or life.get('exit_code')!=0:raise ValueError('Saved processing precedes Native ownership closure')
    if sha(within(folder,life['log']))!=life.get('log_sha256'):raise ValueError('Lifecycle test log changed')
