"""Independent inventory of the unselected current Core primary diagnostics."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def audit():
    records=[]
    for case in ('condition_a','condition_b'):
        log=HERE/'native'/f'current-core-{case}.log'
        receipt=json.loads(log.read_text())
        attempt=Path(receipt['scratch'])/'attempt'
        report=json.loads((attempt/'analysis-report.json').read_text())
        result=json.loads((attempt/'result.json').read_text())
        if (receipt['case']!=case or receipt['render_frames']!=600
            or not receipt['core']['decoder_checked'] or not receipt['final_decode_passed']
            or receipt['derived_channel_count']!=11):
            raise ValueError('Current Core receipt incomplete')
        if result['accepted'] or result['setup_confirmed'] or result['legal_verdict_claimed']:
            raise ValueError('Synthetic diagnostic claims physical success')
        if report['original_joins']['frames']!=600:
            raise ValueError('Original 30-second join incomplete')
        expected=(case=='condition_a')
        if report['measurements']['two_cycle_fault_condition']['value']['two_complete_cycles_waited']!=expected:
            raise ValueError('Controlled cycle contrast differs')
        derived=report['derived_recording_evidence']
        if len(derived['channels'])!=11:
            raise ValueError('Source-derived channel inventory incomplete')
        for name,digest in derived['channels'].items():
            path=attempt/'channels'/(name+'.jsonl')
            channel=rows(path)
            if sha(path)!=digest or len(channel)!=600:
                raise ValueError('Source-derived channel digest/length differs')
            if any(row['native_frame']!=100+i or row['source_sha256']!=derived['source_hashes']
                   for i,row in enumerate(channel)):
                raise ValueError('Source-derived frame/hash join differs')
        if sha(attempt/'context.json')!=derived['context_sha256']:
            raise ValueError('Source-derived context digest differs')
        for name,digest in derived['source_hashes'].items():
            if sha(attempt/name)!=digest:
                raise ValueError('Retained original source differs')
        frames=rows(attempt/'capture/native/frames.jsonl')
        if len(frames)!=600:
            raise ValueError('Current adapter frame list incomplete')
        for row in frames:
            graph=json.loads((attempt/'capture/native'/row['adapter_graph']).read_text())
            if graph['format']!='native-adapter-graph-v1' or graph['metadata']['frame']!=row['frame']:
                raise ValueError('Current adapter graph/frame join differs')
        records.append({'case':case,'log_sha256':sha(log),'analysis_sha256':sha(attempt/'analysis-report.json'),
                        'source_frames':600,'derived_channels':11,'two_cycles_before_turn':expected})
    return {'format':'c110919-current-source-only-core-audit-v1','passed':True,
            'records':records,'selected':False,'native_executed':False,'accepted':False}

if __name__=='__main__':
    value=audit()
    (HERE/'current-core-audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(value['records'])}))
