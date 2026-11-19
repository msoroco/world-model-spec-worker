"""Independently bind all twelve current fallback diagnostic chains."""
import hashlib
import json
from pathlib import Path

from audit_fallback_offline import audit as audit_offline

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'.runtime-work/c179480-update091-v2'
CASES=('reference','contrast','safe_operation_stop','law_required_stop')
CANDIDATES=('fallback1','fallback2','fallback3')
CHECKS={'selected_measurements','negative_case_source','four_camera_sources',
        'native_validation','lean_decoder','render','final_decode'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value,message):
    if not value:raise ValueError(message)


def audit():
    audit_offline()
    records=[]
    for case in CASES:
        manifest_path=HERE/f'draft-{case}-fallback-manifest.json'
        manifest=read(manifest_path)
        entry=manifest['cases'][0]
        require(entry['case_id']==HERE.name+'__'+case and
                len(entry['candidates'])==3,
                'Fallback manifest case or count differs: '+case)
        for candidate in CANDIDATES:
            name=case+'-'+candidate
            selected=next(x for x in entry['candidates'] if x['id']==candidate)
            require(sha(HERE/selected['construction'])==selected['construction_sha256'],
                    'Fallback construction hash differs: '+name)
            attempt=RUN/(name+'-compatibility')
            saved=RUN/(name+'-saved/v0001')
            proof=read(attempt/'compatibility.json')
            revision=read(saved/'processing.json')
            require(proof['passed'] is True and
                    proof['case_id']==entry['case_id'] and
                    proof['candidate_id']==candidate and
                    proof['construction_sha256']==selected['construction_sha256'] and
                    proof['fixture_recipe_sha256']==sha(ROOT/entry['fixture_recipe']) and
                    proof['measurement_contract_sha256']==sha(HERE/entry['measurement_contract']) and
                    CHECKS <= set(proof['checks']),
                    'Pinned fallback compatibility incomplete: '+name)
            require(proof['negative_removed']=='native-map-readback.json' and
                    proof['negative_error_contains'] in
                    (attempt/'negative-analysis.log').read_text(),
                    'Fallback missing-map negative absent: '+name)
            require(revision['passed'] is True and
                    revision['recorded_only'] is True and
                    revision['originals_preserved'] is True and
                    revision['missing_evidence'] is False and
                    revision['candidate_id']==candidate and
                    revision['analysis_revision']['construction_sha256']==
                    selected['construction_sha256'] and
                    revision['timestamp_joins']=={'frames':600,'passed':True,
                      'missing_original_trace_or_map':False} and
                    revision['result_sha256']==sha(saved/'analysis/result.json'),
                    'Recorded-only fallback revision incomplete: '+name)
            require(all(sha(attempt/path)==digest for path,digest in
                        revision['original_source_hashes'].items()),
                    'Saved fallback source hash changed: '+name)
            for result,folder in ((read(attempt/'result.json'),attempt),
                                  (read(saved/'analysis/result.json'),saved/'analysis')):
                trace=(folder/'trace.jsonl').read_text().splitlines()
                require(len(trace)==600 and
                        all(json.loads(line)['speed_provenance']==
                            'synthetic_native_sample' for line in trace) and
                        len(result['video_references'])==4 and
                        result['provenance_kind']=='synthetic_fixture' and
                        result['accepted'] is False and
                        result['maneuver_completed'] is False and
                        result['legal_verdict_claimed'] is False,
                        'Fallback result overclaims acceptance or omits sources: '+name)
                names={x['name'] for x in result['recording_evidence']}
                if case=='safe_operation_stop':
                    require({'hazard_actor_state','ego_hazard_gap_history'} <= names,
                            'Fallback safe-operation channels absent: '+name)
                if case=='law_required_stop':
                    require('governing_control_readback' in names and
                            result['realized_observables']['source_visible_red_control_frames']['value']>0 and
                            result['measured_values']['compliance_with_law']==
                                'independent_original_source_review_required',
                            'Fallback governing control absent or overclaimed: '+name)
            records.append({'case_id':entry['case_id'],'candidate_id':candidate,
                            'construction_sha256':selected['construction_sha256'],
                            'offline_selection_sha256':sha(RUN/'fallbacks-v4'/name/'candidate-selection.json'),
                            'compatibility_sha256':sha(attempt/'compatibility.json'),
                            'saved_processing_sha256':sha(saved/'processing.json')})
    report={'format':'c179480-twelve-fallback-diagnostic-audit-v1',
            'fallbacks':records,'count':len(records),
            'offline_passed':True,'positive_negative_compatibility_passed':True,
            'recorded_only_saved_passed':True,
            'provenance_kind':'synthetic_fixture',
            'canonical_selected':False,
            'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}
    output=HERE/'update091-v4-fallback-matrix-audit.json'
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return {'passed':True,'count':len(records),'audit_sha256':sha(output)}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
