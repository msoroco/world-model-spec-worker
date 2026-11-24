"""Independently audit the unselected current Core green-arrow diagnostics."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE_NAMES={'native':'native_samples.jsonl','map':'video_frames.jsonl',
              'trace':'trace.jsonl','evidence':'capture/evidence.jsonl',
              'body':'body_history.jsonl','config':'config.json',
              'road_geometry':'road_geometry.json'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def audit():
    records=[]
    for case in ('witness_1','witness_2'):
        log=HERE/'native'/f'current-core-{case}.log'
        receipt=json.loads(log.read_text())
        attempt=Path(receipt['scratch'])/'attempt'
        report=json.loads((attempt/'analysis-report.json').read_text())
        result=json.loads((attempt/'result.json').read_text())
        if (receipt['case']!=case or receipt['render_frames']!=600
            or not receipt['core']['decoder_checked'] or not receipt['final_decode_passed']
            or receipt['derived_channel_count']!=10):
            raise ValueError('Current Core diagnostic incomplete')
        if result['accepted'] or result['setup_confirmed'] or result['legal_verdict_claimed']:
            raise ValueError('Synthetic diagnostic claims physical acceptance')
        if report['original_joins']['frames']!=600:
            raise ValueError('Original 30-second frame join incomplete')
        observed=report['measurements']['right_turn_arrow_and_yield']['value']['yielded_to_pedestrian']
        if observed!=(case=='witness_1'):
            raise ValueError('Controlled pedestrian yield contrast differs')
        derived=report['derived_channels']
        if derived['mode']!='raw_native_30s' or len(derived['channel_hashes'])!=10:
            raise ValueError('Raw-derived channel set incomplete')
        for name,digest in derived['channel_hashes'].items():
            path=attempt/'channels'/(name+'.jsonl')
            if sha(path)!=digest or len(rows(path))!=600:
                raise ValueError('Raw-derived channel digest/frame count differs')
        for name,digest in derived['source_hashes'].items():
            if sha(attempt/SOURCE_NAMES[name])!=digest:
                raise ValueError('Retained source digest differs')
        frames=rows(attempt/'capture/native/frames.jsonl')
        if len(frames)!=600:
            raise ValueError('Current adapter frame inventory incomplete')
        for row in frames:
            graph=json.loads((attempt/'capture/native'/row['adapter_graph']).read_text())
            if graph['format']!='native-adapter-graph-v1' or graph['metadata']['frame']!=row['frame']:
                raise ValueError('Current adapter graph/frame join differs')
        records.append({'case':case,'log_sha256':sha(log),
                        'analysis_sha256':sha(attempt/'analysis-report.json'),
                        'frames':600,'derived_channels':10,'yielded_to_pedestrian':observed})
    return {'format':'c110919-3a-current-source-only-core-audit-v1',
            'passed':True,'records':records,'selected':False,
            'native_executed':False,'accepted':False}

if __name__=='__main__':
    value=audit()
    (HERE/'current-core-audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(value['records'])}))
