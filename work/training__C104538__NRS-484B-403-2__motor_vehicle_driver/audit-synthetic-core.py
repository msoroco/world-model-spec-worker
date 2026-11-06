"""Independent source/receipt audit of two unselected synthetic Core paths."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    summary=[]
    for suffix,expected in (('witness_1',False),('witness_2',True)):
        log=FOLDER/('synthetic-core-'+suffix+'.log')
        receipt=json.loads(log.read_text())
        if (receipt['case']!=suffix or receipt['candidate']!='primary' or
            receipt['render_frames']!=480 or receipt['final_decode_passed'] is not True or
            receipt['core']['decoder_checked'] is not True):
            raise AssertionError('Synthetic Core/decoder/render receipt incomplete')
        attempt=Path(receipt['scratch'])/'attempt'
        if not attempt.is_dir():raise AssertionError('Original synthetic attempt missing')
        analysis=json.loads((attempt/'analysis-report.json').read_text())
        result=json.loads((attempt/'result.json').read_text())
        selected=json.loads((attempt/'candidate-selection.json').read_text())
        if selected['case_id']!=result['case_id'] or selected['candidate_id']!='primary':
            raise AssertionError('Exact package identity changed')
        measured=analysis['measurements']['signed_u_turn']['value']
        if measured['u_turn_within_governed_region_observed'] is not expected:
            raise AssertionError('Controlled signed U-turn result changed')
        if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
            raise AssertionError('Synthetic integration claimed acceptance or legal verdict')
        sources=rows(attempt/'native_samples.jsonl')
        mapping=rows(attempt/'video_frames.jsonl')
        frames=rows(attempt/'capture/native/frames.jsonl')
        if (not all(len(value)==480 for value in (sources,mapping,frames)) or
            any(frame.get('synthetic_diagnostic') is not True for frame in frames)):
            raise AssertionError('Full original-shaped synthetic source inventory missing')
        decode=json.loads((attempt/'final-decode.json').read_text())
        if decode['passed'] is not True or decode['frames']!=480:
            raise AssertionError('Final video decode receipt incomplete')
        summary.append({'case':suffix,'synthetic_signed_u_turn':expected,
                        'frames':480,'core_decoder_passed':True,'render_decode_passed':True})
    source_attempt=Path(json.loads((FOLDER/'synthetic-core-witness_1.log').read_text())['scratch'])/'attempt'
    with tempfile.TemporaryDirectory() as temp:
        negative=Path(temp)/'negative'
        shutil.copytree(source_attempt,negative,ignore=shutil.ignore_patterns('converted','traffic_spec','raw.mkv'))
        trace=rows(negative/'trace.jsonl')
        trace[0]['frame']+=1
        (negative/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
        (negative/'analysis-report.json').unlink()
        (negative/'result.json').unlink()
        failure=subprocess.run([sys.executable,str(negative/'finalize.py'),
            '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
            cwd=negative,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        if failure.returncode==0 or 'Original Native/Core frame identity differs' not in failure.stdout:
            raise AssertionError('Changed Core trace frame identity was accepted')
    return {'passed':True,'cases':summary,'changed_trace_frame_rejected':True,
            'selected':False,'native_executed':False,'accepted_recordings':0}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
