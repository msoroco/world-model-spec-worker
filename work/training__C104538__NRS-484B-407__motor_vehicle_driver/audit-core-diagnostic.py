"""Independent source/receipt audit of the synthetic Core and render probe."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
FIXTURE=REPO/'.runtime-work/c104538/core-diagnostic-v2/below_500_ft/positive'
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.adapter import load_graph

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def audit():
    summary=json.loads((ROOT/'core-diagnostic-summary.json').read_text())
    case=ROOT.name+'__below_500_ft'
    assert summary['format']=='c104538-synthetic-core-diagnostic-v1'
    assert summary['case_id']==case and summary['frames']==480
    assert summary['synthetic'] is True and summary['selected'] is False
    assert summary['accepted'] is False and summary['physical_visibility_proven'] is False
    assert sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json')==summary['pinned_runtime_manifest_sha256']
    assert sha(REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')==summary['lean_decoder_sha256']
    manifest=json.loads((FIXTURE/'capture/manifest.json').read_text())
    assert manifest['synthetic_fixture'] is True and manifest['frames']==480
    assert manifest['case_id']==case and manifest['source_run'].startswith('synthetic:')
    config=json.loads((FIXTURE/'config.json').read_text())
    assert config['case_id']==case and config['candidate_id']=='primary'
    trace=rows(FIXTURE/'trace.jsonl');evidence=rows(FIXTURE/'capture/evidence.jsonl')
    graphs=rows(FIXTURE/'capture/native/frames.jsonl')
    mapping=rows(FIXTURE/'video_frames.jsonl')
    assert len(trace)==len(evidence)==len(graphs)==len(mapping)==480
    assert sha(FIXTURE/'trace.jsonl')==summary['provenance']['trace_sha256']
    assert sha(FIXTURE/'capture/evidence.jsonl')==summary['provenance']['evidence_sha256']
    assert sha(FIXTURE/'raw.mkv')==summary['provenance']['raw_video_sha256']
    for index,(t,e,g,m) in enumerate(zip(trace,evidence,graphs,mapping)):
        frame=1001+index;time=round((index+1)/20,4)
        assert t['frame']==e['original_frame']==e['replay_frame']==g['frame']==m['carla_frame']==frame
        assert t['time_s']==e['recording_time_s']==m['time_s']==time
        assert m['video_frame']==index
        graph=load_graph(FIXTURE/'capture/native'/g['base'])
        assert graph.graph['frame']==frame
        assert graph.graph['observed_evidence']==e['original_observations']
    converted=FIXTURE/'converted'
    assert sha(converted/'trace.json')==summary['core_trace_sha256']
    assert sha(converted/'adapter_report.json')==summary['adapter_report_sha256']
    scenes=json.loads((converted/'trace.json').read_text())['scenes']
    assert len(scenes)==480
    report=json.loads((converted/'adapter_report.json').read_text())
    assert report['required_measurements_complete'] is True
    assert not report['atom_coverage']['missing']
    review=json.loads((FIXTURE/'event_review.json').read_text())
    assert sha(FIXTURE/'event_review.json')==summary['review_receipt_sha256']
    assert sha(FIXTURE/'event_review.webm')==summary['review_video_sha256']==review['video_sha256']
    assert sha(FIXTURE/'event_review_frames.jsonl')==summary['review_frame_map_sha256']==review['frame_map_sha256']
    assert review['frames']==480 and review['source_frame_interval']==[0,479]
    assert review['coverage_kind']=='full_delivered_trace'
    review_map=rows(FIXTURE/'event_review_frames.jsonl')
    assert len(review_map)==480 and [r['source_video_frame'] for r in review_map]==list(range(480))
    probe=REPO/'.runtime-work/linux_arm64/ffprobe'
    decode=subprocess.run([str(probe),'-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
        str(FIXTURE/'event_review.webm')],capture_output=True,text=True,check=True,timeout=120)
    assert decode.stdout.strip()=='480'
    negative=REPO/'.runtime-work/c104538/core-diagnostic-v2/below_500_ft/negative_missing_native_frames'
    assert not (negative/'capture/native/frames.jsonl').exists()
    assert summary['negative_exit_code']!=0
    for label,spec in summary['logs'].items():
        log=ROOT/spec['path']
        assert sha(log)==spec['sha256']
        if label=='negative_missing_native_frames':
            assert 'capture/native/frames.jsonl' in log.read_text()
    return {'case_id':case,'core_scenes':len(scenes),'decoded_review_frames':480,
            'required_observations':len(report['required_observations']),
            'negative_rejections':1,'selected':False,'accepted':False}

if __name__=='__main__':print(json.dumps(audit()))
