"""Test the source-shape antecedent that the entering driver first yielded."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import json
import os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'/'c111294-entrant-antecedent'

def module(path,name):
    spec=spec_from_file_location(name,path);m=module_from_spec(spec);spec.loader.exec_module(m);return m

SOURCE=module(HERE/'prove-yield-sequence.py','c111294_existing_fixture')
METER=module(HERE/'native'/'measure_yield.py','c111294_existing_meter')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run():
    output_root=Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT','')).resolve()
    assert ROOT/'.runtime-work' in output_root.parents
    SCRATCH.mkdir(parents=True,exist_ok=True)
    case=HERE.name+'__probe_1'
    baseline=SOURCE.rows(True)
    base=SCRATCH/'baseline';SOURCE.write_fixture(base,case,baseline)
    positive=METER.measure(base,case)
    assert positive['entrant_prior_stopped_frames']>=40 and positive['through_yield_response_observed']
    negatives=[]
    for label,frames in (('no_prior_stop',range(140)),('single_frame_stop',range(1,140))):
        modified=json.loads(json.dumps(baseline))
        for i in frames:
            modified[i]['entrant']['speed_mps']=1.0
            modified[i]['entrant']['x_m']=-12+i*.002
        folder=SCRATCH/label;SOURCE.write_fixture(folder,case,modified)
        try:METER.measure(folder,case)
        except ValueError as exc:
            assert str(exc)=='Entrant prior yield and about-to-enter sequence absent',str(exc)
            negatives.append({'label':label,'source_sha256':sha(folder/'native_samples.jsonl'),'rejection':str(exc)})
        else:raise AssertionError('Missing entrant antecedent accepted: '+label)
    missing=SCRATCH/'missing_entrant_history'
    modified=json.loads(json.dumps(baseline));modified[150].pop('entrant')
    SOURCE.write_fixture(missing,case,modified)
    try:METER.measure(missing,case)
    except ValueError as exc:
        assert str(exc)=='Two participant histories required',str(exc)
        negatives.append({'label':'missing_entrant_history','source_sha256':sha(missing/'native_samples.jsonl'),'rejection':str(exc)})
    else:raise AssertionError('Missing entrant history accepted')
    receipt={'format':'c111294-entrant-antecedent-proof-v1','case_id':case,'frames':600,'rate_hz':20,
             'positive_source_sha256':sha(base/'native_samples.jsonl'),
             'positive_prior_stopped_frames':positive['entrant_prior_stopped_frames'],
             'negative_rejections':negatives,'meter_sha256':sha(HERE/'native'/'measure_yield.py'),
             'physical_observation_claimed':False,'lawful_prior_yield_verified':False,'legal_verdict_claimed':False}
    out=HERE/'entrant-antecedent-proof.json';out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'positive_passed':True,'negative_count':len(negatives),'proof_sha256':sha(out)}))

if __name__=='__main__':run()
