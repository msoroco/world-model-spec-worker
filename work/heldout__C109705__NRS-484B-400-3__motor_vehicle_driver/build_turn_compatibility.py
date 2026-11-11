"""Bind case-specific synthetic source diagnostics and exact turn measurements."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(path):return json.loads(Path(path).read_text())
def write(path, obj):Path(path).write_text(json.dumps(obj, indent=2)+'\n')
def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def main():
    base = read(REPO/'work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/diagnostic-person_3mps.json')
    for name in ('alley_context.json', 'participant_footprints.jsonl', 'ego_motion.jsonl'):
        base['files'].pop(name, None)
    base['files']['fixture-provenance.json'] = json.dumps({
        'provenance_kind': 'synthetic_fixture',
        'scope': 'C109705 turn software diagnostic only; no Native left turn or one-way road established'})+'\n'
    plan_path=ROOT/'case-plan.json';plan=read(plan_path)
    plan['requirement_dispositions']=[{'requirement':
        'Original right-half approach, centerline entry and one-way left-curb departure positions',
        'source':str((REPO/'inputs'/ROOT.name/'assignment.json').relative_to(REPO)),
        'status':'selected_required','case_ids':[x['case_id'] for x in plan['cases']],
        'evidence_or_gap':'No accepted originals; exact CPU diagnostics preserve legal practicability uncertainty.'}]
    write(plan_path,plan)
    constructions=read(ROOT/'construction-probe-manifest.json')
    source_description=read(ROOT/'cases/construction-centerline_approach_left_curb_departure-primary.json')['recording_description']
    proposal_cases=[]; manifest_cases=[]
    for entry in constructions['cases']:
        case=entry['case_id'];suffix=case.split('__')[-1]
        proposal_cases.append({'case_id':case,'target_law_id':'NRS-484B-400-3',
            'target_type':'controlled_comparison',
            'rationale':'Original full-body left-turn positions; no legal lateral cutoff.',
            'variable_assignments':{'turn_variant':{'kind':'controller','value':suffix}},
            'unresolved_judgment_calls':['as close as practicable'],
            'recording_description':source_description})
        source=json.loads(json.dumps(base))
        trace=[json.loads(x) for x in source['files']['trace.jsonl'].splitlines()]
        frames=[json.loads(x) for x in source['files']['video_frames.jsonl'].splitlines()]
        survey=read(ROOT/'turn-route-survey.json')
        geometry={'case_id':case,'ego_actor_id':205,
            'approach_directions':2,'destination_directions':1,
            'maneuver':'left_turn','intersection_kind':'public_highway_non_alley',
            'approach_centerline_xy_m':[[99,0],[99,10]],
            'destination_left_curb_xy_m':[[97,2],[87,2]],
            'intersection_entry_xy_m':[99,10],
            'survey_source_sha256':digest(ROOT/'turn-route-survey.json'),
            'fixture_note':'Synthetic turn-body rows; not Native travel or physical highway facts.'}
        bodies=[]
        for i,(state,frame) in enumerate(zip(trace,frames)):
            x=100.0+(0.65 if suffix.startswith('farther_approach') else 0)
            y=1.6+(0.65 if suffix.endswith('farther_departure') and i>=6 else 0)
            corners=[[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]]
            bodies.append({'frame':frame['carla_frame'],'time_s':frame['time_s'],
                'actor_id':205,'phase':('approach' if i<3 else 'entry' if i<6 else 'departure'),
                'body_corners_xy_m':corners})
        source['files']['turn_road_geometry.json']=json.dumps(geometry)+'\n'
        source['files']['body_footprints.jsonl']=''.join(json.dumps(x)+'\n' for x in bodies)
        fixture=ROOT/f'diagnostic-{suffix}.json';fixture.write_text(json.dumps(source,separators=(',',':'))+'\n')
        recipe=ROOT/f'diagnostic-recipe-{suffix}.json'
        write(recipe,{'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':str(fixture.relative_to(REPO)),
                        'sha256':digest(fixture)}],
            'generator':{'source':str(fixture.relative_to(REPO)),'sha256':digest(fixture)}})
        contract=ROOT/'cases'/f'measurement-contract-{suffix}.json'
        write(contract,{'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,
                'requirement':plan['requirement_dispositions'][0]['requirement'],
                'source':plan['requirement_dispositions'][0]['source'],
                'output_key':'turn_original_position','method':'measure_turn',
                'value_type':'object','kind':'measured',
                'inputs':['turn_road_geometry.json','body_footprints.jsonl','video_frames.jsonl']}],
            'negative':{'remove':['body_footprints.jsonl'],
                        'error_contains':'Missing required source: body_footprints.jsonl'}})
        manifest_cases.append({**entry,'kind':'delivery',
            'measurement_contract':str(contract.relative_to(ROOT)),
            'measurement_procedure':{'entrypoint':'turn_finalizer.py'},
            'fixture_recipe':str(recipe.relative_to(REPO)),
            'acquisition':{'turn_centerline_offset':{
                'entrypoint':'turn_finalizer.py',
                'method':'original full-body corners and directed centerline projected after capture',
                'evidence':'body_footprints.jsonl, turn_road_geometry.json and video_frames.jsonl'}}})
    (ROOT/'proposals').mkdir(exist_ok=True)
    write(ROOT/'proposals/cases.json',{'format':'worker-scenario-cases','cases':proposal_cases})
    write(ROOT/'probe-compatibility-manifest.json',{'format':'worker-compatibility-manifest',
        'assignment_id':ROOT.name,
        'runtime_manifest_sha256':digest(REPO/'runtime/SOURCE-MANIFEST.json'),
        'cases':manifest_cases})
    print('Three exact turn diagnostic recipes and measurement contracts bound')


if __name__=='__main__':main()
