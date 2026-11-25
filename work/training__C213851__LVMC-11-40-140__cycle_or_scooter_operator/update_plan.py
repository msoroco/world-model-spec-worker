"""Describe exact source-gated sidewalk coverage and controlled comparison."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name


def main():
    plan=json.loads((HERE/'case-plan.json').read_text())
    plan['selected_branch']='Entering a driveway across a sidewalk area.'
    manifest=json.loads((HERE/'selected-offline-manifest.json').read_text())
    entries={item['case_id']:item for item in manifest['cases']}
    for case in plan['cases']:
        cid=case['case_id']
        suffix=cid.rsplit('__',1)[-1]
        source=entries[cid]
        case.update(kind='delivery',selection_status='selected',expected_label=None,
            construction_status='pinned_offline_passed_original_native_unexecuted',
            construction_path=source['construction'],
            construction_sha256=source['construction_sha256'],
            fixture_recipe=f'cases/{suffix}/recipe.json',
            selection_targets=['full-train'],requested_not_measured=True,
            selection_reason='No accepted full-train evidence; selected residence-driveway bicycle comparison requires original stop and pedestrian conflict sources.',
            gap_ids=[])
        if suffix=='probe_01':
            case['physical_target']='enter driveway after stopping before surveyed sidewalk and yielding until pedestrian clears conflict region'
        else:
            case['physical_target']='enter same driveway by rolling through surveyed sidewalk boundary while pedestrian conflict persists'
    plan['comparisons']=[{'comparison_id':AID+'__stop_yield_comparison',
        'case_ids':[AID+'__probe_01',AID+'__probe_02'],
        'deliberate_differences':['commanded pre-sidewalk stop and pedestrian crossing timing'],
        'fixed_conditions':['frozen residence-district driveway cell and bicycle actor',
            'same surveyed sidewalk continuation, boundary and pedestrian conflict polygon',
            'same bicycle and pedestrian identities, route, 20 Hz rate and 30 s capture',
            'same four-camera source profile and recording description']}]
    plan['requirement_dispositions'][0]['evidence_or_gap']='Two exact residence-driveway bicycle cases compare source-measured pre-sidewalk cessation and pedestrian conflict timing; no legal numeric cutoff or physical outcome is inferred.'
    source=f'inputs/{AID}/assignment.json'
    plan['source_observation_mapping']={item['term']:{
        'evidence':'Original Native rider/pedestrian pose joined to independently reviewed district, driveway, sidewalk and conflict sources; legal judgment reserved',
        'channels':[item['term']],'source_refs':[source]}
        for item in plan['source_observation_terms']}
    plan['camera_plan']={'profile':'overview1080-capability','duration_s':30,
        'composition':'synchronized_four_view_primary',
        'coverage':[{'view':name,
            'subject':'bicycle, sidewalk boundary and pedestrian conflict region',
            'interval':'full 30 s capture'}
            for name in ('overview','approach','reference_corner','driver_reference')]}
    plan['selected_delivery_case_count']=2
    plan['runtime_gaps']=['Original surveyed district, driveway, sidewalk continuation, rider suitability, pedestrian conflict and physical motion remain to be reviewed after Native capture.']
    plan['runtime_uncertainties']=['No CARLA execution or accepted recording is claimed; original sidewalk, bicycle and pedestrian conditions remain source-gated.']
    (HERE/'case-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':
    main()
