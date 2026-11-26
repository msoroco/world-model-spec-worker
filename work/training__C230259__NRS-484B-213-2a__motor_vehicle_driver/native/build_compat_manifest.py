"""Bind exact selected constructions, synthetic fixtures and source contracts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((ROOT / 'selected-construction-draft.json').read_text())
    entries = selected['cases']
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    disposition = plan['requirement_dispositions'][0]
    proposal_cases = []
    for suffix, entry in zip(SUFFIXES, entries):
        case_id = entry['case_id']
        construction = json.loads((ROOT / entry['construction']).read_text())
        entry['fixture_recipe'] = 'work/' + ROOT.name + '/selected-fixtures/' + suffix + '/fixture-recipe.json'
        entry['measurement_procedure'] = {'entrypoint':'finalize.py', 'output_schema':'worker-feature-source-measurement-v1'}
        entry['recording_description'] = construction['recording_description']
        contract = {'format':'worker-measurement-contract', 'case_id':case_id,
                    'requirements':[{'disposition_index':0,
                        'requirement':disposition['requirement'],
                        'source':disposition['source'],
                        'kind':'measured', 'method':'measure_feature',
                        'output_key':'feature', 'value_type':'object',
                        'inputs':['native-feature-source.jsonl','road-context.json',
                                  'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl']}],
                    'negative':{'remove':['native-feature-source.jsonl'],
                                'error_contains':'Missing required source: native-feature-source.jsonl'},
                    'status':'selected_delivery_cpu_prepared'}
        contract_path = ROOT / 'selected-fixtures' / suffix / 'measurement-contract.json'
        contract_path.write_text(encode(contract))
        entry['measurement_contract'] = str(contract_path.relative_to(ROOT))
        target_type = ('compliant_attempt' if suffix in ('probe_a','curve_right','one_way_crest','one_way_curve')
                       else 'violating_attempt')
        proposal_cases.append({'case_id':case_id,'target_law_id':'NRS-484B-213-2a',
            'target_type':target_type,
            'rationale':'Source-grounded physical request for '+suffix+'; no legal verdict or hazard threshold assigned',
            'variable_assignments':{
                'feature_kind':{'kind':'world_setup','value':'curve' if 'curve' in suffix else 'crest','unit':'categorical'},
                'road_directionality':{'kind':'world_setup','value':'one_way' if suffix.startswith('one_way') else 'two_way','unit':'categorical'},
                'left_of_center_request':{'kind':'controller','value':suffix not in ('probe_a','curve_right'),'unit':'boolean'},
                'observed_left_of_center':{'kind':'subject_behavior','value':None,'unit':'per frame'},
                'observed_sightline':{'kind':'subject_behavior','value':None,'unit':'meters with censor status'}},
            'unresolved_judgment_calls':['Hazard-creating obstruction distance and original highway authority require source review'],
            'paired_probe_id':ROOT.name+'__'+('curve' if 'curve' in suffix else 'crest')+'_contrast',
            'deliberate_differences':['left_of_center_request'] if suffix in ('probe_a','probe_b','curve_right','curve_left') else ['road_directionality'],
            'probe':{'primary_variable':'road_directionality' if suffix.startswith('one_way') else 'left_of_center_request',
                     'comparison_or_standard':'controlled contrast; legal judgment deferred',
                     'target_value_or_branch':suffix},
            'recording_description':construction['recording_description']})
    proposal = {'cell_id':'C230259','actor':'motor_vehicle_driver','status':'draft',
                'cases':proposal_cases,'sweep_specs':[]}
    (ROOT / 'proposals').mkdir(exist_ok=True)
    (ROOT / 'proposals/cases.json').write_text(encode(proposal))
    manifest = {'format':'worker-unselected-draft-construction-manifest-v1',
                'assignment_id':ROOT.name,
                'runtime_manifest_sha256':sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status':'selected_cpu_compatibility_probe', 'cases':entries}
    target=ROOT/'selected-compatibility-manifest.json'
    target.write_text(encode(manifest))
    print(json.dumps({'manifest_sha256':sha(target),'cases':len(entries)}))


if __name__=='__main__':
    main()
