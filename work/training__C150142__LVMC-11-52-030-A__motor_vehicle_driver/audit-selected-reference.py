"""Independent CPU review of reference candidate and saved receipt bindings."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate as validate_candidates


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value,message):
    if not value:raise ValueError(message)


def audit():
    index=json.loads((ROOT/'selected-reference-receipts/proof-index.json').read_text())
    case=ROOT.name+'__reference'
    require(index['case_id']==case and index['candidate_count']==4 and
            index['original_native_observed'] is False and
            set(index['candidates'])=={'primary','fallback1','fallback2','fallback3'},
            'Reference candidate index differs')
    baseline=None;outcomes={};negative=[]
    for candidate,row in index['candidates'].items():
        manifest=ROOT/row['manifest'];construction=ROOT/row['construction']
        require(sha(manifest)==row['manifest_sha256'] and
                sha(construction)==row['construction_sha256'],
                'Selected construction or manifest changed: '+candidate)
        m=json.loads(manifest.read_text());entry=m['cases'][0]
        require(entry['case_id']==case and
                sha(REPO/entry['fixture_recipe'])==row['fixture_recipe_sha256'],
                'Case identity or fixture recipe differs: '+candidate)
        validate_candidates(ROOT,entry,'LVMC-11-52-030-A','C150142',candidate_count=4)
        cfg=json.loads(next(item['content'] for item in
            json.loads(construction.read_text())['files'] if item['path']=='config.json'))
        fixed={key:cfg[key] for key in ('cell_id','law_id','actor','selected_case_id',
            'required_atoms','source_packets','rate_hz','duration_s','cameras')}
        if baseline is None:baseline=fixed
        require(fixed==baseline and cfg['candidate_id']==candidate,
                'Fallback changed selected case or capture profile: '+candidate)
        receipts={}
        for name,spec in row['receipts'].items():
            path=ROOT/spec['path']
            require(sha(path)==spec['sha256'],
                    'Retained proof artifact changed: '+candidate+'/'+name)
            receipts[name]=json.loads(path.read_text()) if path.suffix=='.json' else path.read_text()
        for stage,checksum in row['logs'].items():
            require(sha(ROOT/('update019c-'+candidate+'-'+stage+'.log'))==checksum,
                    'Pinned command log changed: '+candidate+'/'+stage)
        require('OK' in receipts['offline_test'] and
                'Missing required source: native-map-readback.json' in
                receipts['negative_analysis'],
                'Offline or missing-source rejection absent: '+candidate)
        compat=receipts['compatibility'];saved=receipts['saved']
        result=receipts['result'];analysis=receipts['analysis']
        require(compat['passed'] is True and compat['candidate_id']==candidate and
                compat['construction_sha256']==row['construction_sha256'] and
                compat['fixture_recipe_sha256']==row['fixture_recipe_sha256'] and
                compat['negative_log_sha256']==row['receipts']['negative_analysis']['sha256'] and
                {'actual_analysis','native_validation','lean_decoder','render',
                 'final_decode','four_camera_sources','selected_measurements',
                 'negative_case_source'}<=set(compat['checks']),
                'Pinned compatibility proof incomplete: '+candidate)
        require(saved['passed'] is True and saved['candidate_id']==candidate and
                saved['analysis_revision']['construction_sha256']==row['construction_sha256'] and
                saved['originals_preserved'] is True and saved['missing_evidence'] is False and
                saved['timestamp_joins']['frames']==240 and
                saved['timestamp_joins']['passed'] is True and
                saved['final_video_checks']['passed'] is True and
                saved['final_video_checks']['frames']==240 and
                saved['result_sha256']==row['receipts']['result']['sha256'],
                'Saved processing proof incomplete: '+candidate)
        require(result['case_id']==case and result['provenance_kind']==
                'synthetic_local_diagnostic' and result['accepted'] is False and
                analysis['source_kind']=='synthetic_native_sample' and
                analysis['physical_acceptance_claimed'] is False and
                result['measured_values']['red_curb_stop_or_park_observed'] is True,
                'Diagnostic result claims Native or changes observation: '+candidate)
        count=result['measured_values']['red_curb_stopped_frames']
        require(count==row['synthetic_red_stopped_frames'],
                'Candidate stopped interval differs: '+candidate)
        outcomes[candidate]=count
        negative.append(candidate)
    require(outcomes=={'primary':119,'fallback1':59,'fallback2':119,'fallback3':149},
            'Candidate timing probes differ')
    return {'format':'c150142-reference-candidate-audit-v1','passed':True,
            'case_id':case,'candidate_count':4,'synthetic_red_stopped_frames':outcomes,
            'negative_sources_checked':negative,'original_native_observed':False,
            'physical_acceptance_claimed':False,'legal_verdict':None}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
