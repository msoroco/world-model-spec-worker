"""Reproduce synthetic CPU physical-outcome diagnostics from a saved source attempt."""
import argparse,hashlib,json,shutil,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(attempt,output):
    attempt=Path(attempt);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    base=json.loads((attempt/'config.json').read_text())
    original=[json.loads(line) for line in (attempt/'trace.jsonl').read_text().splitlines()]
    assert len(original)>=2
    results={}
    for kind in ('complete_motion','incomplete_motion','missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='physical-cpu-') as tmp:
            work=Path(tmp)
            for name in ('config.json','video_frames.jsonl','trace.jsonl'):shutil.copy2(attempt/name,work/name)
            if kind=='complete_motion':
                rows=json.loads(json.dumps(original))
                start=rows[0]['position_m'][0]
                for i,row in enumerate(rows):row['position_m'][0]=start+40*i/(len(rows)-1)
                (work/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            elif kind=='missing_evidence':(work/'trace.jsonl').unlink()
            assessment=assess_physical(work,base)
            expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
            assert assessment['physical_checks']['maneuver']['status']==expected,(kind,assessment['physical_checks']['maneuver'])
            result={'format':'worker-physical-source-protocol-fixture','fixture_kind':kind,'diagnostic_fixture':True,'provenance_kind':'synthetic_fixture','physical_acceptance_claimed':False,'legal_acceptance_claimed':False,**assessment}
            path=output/f'physical-{kind}.json';path.write_text(json.dumps(result,indent=2)+'\n');results[kind]={'sha256':digest(path),'source_hashes':{n:digest(work/n) for n in ('config.json','video_frames.jsonl') if (work/n).exists()},'maneuver_status':expected}
    print(json.dumps({'format':'worker-current-runtime-physical-diagnostic','source_attempt':str(attempt),'source_trace_sha256':digest(attempt/'trace.jsonl'),'runtime_assessor':'worker_exchange.native_output.assess_physical','results':results,'physical_or_legal_acceptance_claimed':False}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.attempt,a.output)
