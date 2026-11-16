"""Independent source-bound audit of the two four-candidate CPU proof sets."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CANDIDATES=('primary','fallback1','fallback2','fallback3')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)

def audit():
    outcomes={};configs={};sources={}
    for witness in ('reference','contrast'):
        index=json.loads((ROOT/('selected-'+witness+'-current-receipts/proof-index.json')).read_text())
        case=ROOT.name+'__'+witness
        require(index['case_id']==case and index['candidate_count']==4 and
                set(index['candidates'])==set(CANDIDATES) and
                index['original_native_observed'] is False and
                index['physical_acceptance_claimed'] is False,
                'Candidate index changed: '+witness)
        outcomes[witness]={};configs[witness]={};sources[witness]={}
        for candidate,row in index['candidates'].items():
            tag=witness+'/'+candidate
            manifest=ROOT/row['manifest'];construction=ROOT/row['construction']
            require(sha(manifest)==row['manifest_sha256'] and
                    sha(construction)==row['construction_sha256'],
                    'Selected source changed: '+tag)
            package=json.loads(construction.read_text())
            cfg=json.loads(next(file['content'] for file in package['files']
                                if file['path']=='config.json'))
            require(package['case_id']==case and cfg['candidate_id']==candidate,
                    'Case or candidate changed: '+tag)
            entry=next(x for x in json.loads(manifest.read_text())['cases']
                       if x['case_id']==case)
            require(sha(REPO/entry['fixture_recipe'])==row['fixture_recipe_sha256'],
                    'Fixture recipe changed: '+tag)
            receipts={}
            for name,spec in row['receipts'].items():
                path=ROOT/spec['path'];require(sha(path)==spec['sha256'],
                       'Retained receipt changed: '+tag+'/'+name)
                receipts[name]=json.loads(path.read_text()) if path.suffix=='.json' else path.read_text()
            for stage,checksum in row['logs'].items():
                require(sha(ROOT/('update021a-'+witness+'-'+candidate+'-'+stage+'.log'))==checksum,
                        'Pinned command log changed: '+tag+'/'+stage)
            compat=receipts['compatibility'];saved=receipts['saved']
            result=receipts['result'];analysis=receipts['analysis']
            require('OK' in receipts['offline_test'] and
                    'Missing required source: native-map-readback.json' in receipts['negative_analysis'],
                    'Positive/negative evidence missing: '+tag)
            require(compat['passed'] is True and saved['passed'] is True and
                    compat['construction_sha256']==row['construction_sha256'] and
                    saved['analysis_revision']['construction_sha256']==row['construction_sha256'] and
                    saved['originals_preserved'] is True and saved['missing_evidence'] is False and
                    saved['timestamp_joins']['frames']==240 and
                    saved['final_video_checks']['frames']==240,
                    'Current compatibility/saved proof incomplete: '+tag)
            observed=result['measured_values']['red_curb_stop_or_park_observed']
            count=result['measured_values']['red_curb_stopped_frames']
            require(result['case_id']==case and result['provenance_kind']=='synthetic_local_diagnostic' and
                    result['accepted'] is False and analysis['source_kind']=='synthetic_native_sample' and
                    analysis['physical_acceptance_claimed'] is False and
                    observed==(witness=='reference') and
                    count==row['synthetic_red_stopped_frames'] and
                    all(x['physical_cause_confirmed'] is False for x in result['target_checks']),
                    'Diagnostic outcome or provenance changed: '+tag)
            configs[witness][candidate]=cfg
            sources[witness][candidate]={file['path']:file['content'] for file in package['files']}
            outcomes[witness][candidate]=count
    require(outcomes['reference']==dict(zip(CANDIDATES,(119,59,119,149))) and
            outcomes['contrast']==dict(zip(CANDIDATES,(0,0,0,0))),
            'Measured interval comparison changed')
    for candidate in CANDIDATES:
        ref=configs['reference'][candidate];contrast=configs['contrast'][candidate]
        omitted={'case_id','selected_case_id','supported_case_ids','requested_target_x_m',
                 'tracks_sha256','assignment_sha256','case_plan_sha256'}
        require({k:v for k,v in ref.items() if k not in omitted}==
                {k:v for k,v in contrast.items() if k not in omitted},
                'Uncontrolled setting changed: '+candidate)
        require(ref['requested_target_x_m']==40 and contrast['requested_target_x_m']==60,
                'Requested contrast changed: '+candidate)
        fixed_files=('red-curb-road.xodr','parking_controller.py','finalize_selected.py',
                     'measure_red_curb.py')
        require(all(sources['reference'][candidate][key]==sources['contrast'][candidate][key]
                    for key in fixed_files),'Fixed source changed: '+candidate)
    return {'format':'c150142-current-diagnostic-comparison-audit-v1',
            'passed':True,'cases':2,'candidates_per_case':4,'counts':outcomes,
            'original_native_observed':False,'physical_acceptance_claimed':False,
            'legal_verdict':None}

if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
