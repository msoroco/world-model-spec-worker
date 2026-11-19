"""Independently bind all four current draft primary diagnostic chains."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT/'.runtime-work/c179480-update091-v2'
CASES = {'reference':'reference', 'contrast':'contrast',
         'safe_operation_stop':'safe', 'law_required_stop':'law'}
REQUIRED_CHECKS = {'selected_measurements', 'negative_case_source',
                   'four_camera_sources', 'native_validation',
                   'lean_decoder', 'render', 'final_decode'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit():
    proposals = read(HERE/'proposals/cases.json')
    require({item['case_id'] for item in proposals['cases']} ==
            {HERE.name+'__'+case for case in CASES}, 'Four proposals differ')
    records=[]
    for case, stem in CASES.items():
        case_id=HERE.name+'__'+case
        manifest_path=HERE/f'draft-{case}-compatibility-manifest.json'
        manifest=read(manifest_path)
        require(len(manifest['cases'])==1 and
                manifest['cases'][0]['case_id']==case_id,
                'Diagnostic manifest differs: '+case)
        entry=manifest['cases'][0]
        require(sha(HERE/entry['construction'])==entry['construction_sha256'],
                'Construction hash differs: '+case)
        offline_manifest=(HERE/('draft-law-required-manifest.json'
                                 if case=='law_required_stop' else
                                 'draft-reference-manifest.json'))
        selection=read(RUN/f'{case}-primary-offline/candidate-selection.json')
        require(selection['case_id']==case_id and
                selection['candidate_id']=='primary' and
                selection['construction_sha256']==entry['construction_sha256'] and
                selection['manifest_sha256']==sha(offline_manifest),
                'Current offline selection incomplete: '+case)
        attempt=RUN/f'{stem}-primary-compatibility'
        saved=RUN/f'{stem}-primary-saved/v0001'
        compatibility=read(attempt/'compatibility.json')
        processing=read(saved/'processing.json')
        original=read(attempt/'result.json')
        revision=read(saved/'analysis/result.json')
        require(compatibility['passed'] is True and
                compatibility['case_id']==case_id and
                compatibility['candidate_id']=='primary' and
                compatibility['construction_sha256']==entry['construction_sha256'] and
                compatibility['runtime_manifest_sha256']==manifest['runtime_manifest_sha256'] and
                REQUIRED_CHECKS <= set(compatibility['checks']),
                'Current compatibility incomplete: '+case)
        require(compatibility['fixture_recipe_sha256']==sha(ROOT/entry['fixture_recipe']) and
                compatibility['measurement_contract_sha256']==sha(HERE/entry['measurement_contract']),
                'Diagnostic sources unbound: '+case)
        require(compatibility['negative_removed']=='native-map-readback.json' and
                compatibility['negative_error_contains'] in
                (attempt/'negative-analysis.log').read_text(),
                'Missing-map negative did not reject: '+case)
        require(processing['passed'] is True and
                processing['recorded_only'] is True and
                processing['originals_preserved'] is True and
                processing['missing_evidence'] is False and
                processing['candidate_id']=='primary' and
                processing['timestamp_joins']=={'frames':600,'passed':True,
                  'missing_original_trace_or_map':False} and
                processing['analysis_revision']['construction_sha256']==entry['construction_sha256'] and
                processing['result_sha256']==sha(saved/'analysis/result.json'),
                'Recorded-only revision incomplete: '+case)
        require(all(sha(attempt/name)==digest for name,digest in
                    processing['original_source_hashes'].items()),
                'Saved source hash changed: '+case)
        for result, folder in ((original,attempt),(revision,saved/'analysis')):
            trace=(folder/'trace.jsonl').read_text().splitlines()
            require(len(trace)==600 and len(result['video_references'])==4 and
                    result['case_id']==case_id and
                    result['provenance_kind']=='synthetic_fixture' and
                    result['accepted'] is False and
                    result['maneuver_completed'] is False and
                    result['legal_verdict_claimed'] is False,
                    'Result overclaims or omits diagnostic source: '+case)
            require(all(json.loads(line)['speed_provenance']=='synthetic_native_sample'
                        for line in trace),
                    'Invented speed claimed original provenance: '+case)
            names={item['name'] for item in result['recording_evidence']}
            if case=='safe_operation_stop':
                require({'hazard_actor_state','ego_hazard_gap_history'} <= names,
                        'Safe source channels absent')
            if case=='law_required_stop':
                require('governing_control_readback' in names and
                        result['realized_observables']['source_visible_red_control_frames']['value']>0 and
                        result['measured_values']['compliance_with_law']==
                            'independent_original_source_review_required',
                        'Governing control evidence absent or overclaimed')
        records.append({'case_id':case_id,
                        'offline_selection_sha256':sha(
                            RUN/f'{case}-primary-offline/candidate-selection.json'),
                        'manifest_sha256':sha(manifest_path),
                        'construction_sha256':entry['construction_sha256'],
                        'recipe_sha256':sha(ROOT/entry['fixture_recipe']),
                        'compatibility_sha256':sha(attempt/'compatibility.json'),
                        'saved_processing_sha256':sha(saved/'processing.json')})
    report={'format':'c179480-four-draft-primary-diagnostic-audit-v1',
            'cases':records,'positive_negative_compatibility_passed':True,
            'recorded_only_saved_passed':True,
            'synthetic_source_frames_per_case':600,
            'source_cameras_per_case':4,
            'canonical_selected':False,
            'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False,
            'scope':'four draft primaries; candidate fallbacks and final audits unproved'}
    output=HERE/'update091-v2-four-primary-audit.json'
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return {'passed':True,'audit_sha256':sha(output),'cases':len(records)}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
