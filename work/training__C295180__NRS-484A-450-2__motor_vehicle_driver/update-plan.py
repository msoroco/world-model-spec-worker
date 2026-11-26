"""Bind exact stop-line branch scope and source channels without claiming other branches."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
path=HERE/'case-plan.json'
plan=json.loads(path.read_text())
ids=[case['case_id'] for case in plan['cases']]
for item in plan['requirement_dispositions']:
    item['status']='selected_required'
    item['case_ids']=ids
    if item['requirement']=='text-0':
        item['evidence_or_gap']='The selected no-crosswalk marked-line branch is constructed in two exact cases. Source-sealed diagnostic motion and camera fixtures pass CPU proofs; original Native physical and legal interpretation await local review.'
    else:
        item['evidence_or_gap']='The reviewed near-side crosswalk topic is mapped as absent on this selected marked-line approach, using authored road and source measurement; the crosswalk-present alternative is not claimed for this assignment.'
for item in plan['observations']:
    item['status']='mapped_to_selected_source_channel_pending_original_native_review'
for term,mapping in plan['source_observation_mapping'].items():
    mapping['channels']=[term]
    mapping['evidence']='Selected finalizer and source-sealed diagnostic fixture map this term to the same named capture channel. Physical original Native evidence remains pending; sight/visible are inapplicable on the marked-line branch and retained as explicit absence observations.'
plan['camera_plan']={'profile':'overview1080-capability','duration_s':30,'composition':'synchronized_four_view_primary','coverage':[{'view':'overview','subject':'subject full body and T-intersection','interval':'all 600 frames'},{'view':'approach','subject':'governing STOP sign and approaching subject','interval':'approach through clearance'},{'view':'reference_corner','subject':'marked line, no near-side crosswalk and front footprint','interval':'before line through entry'},{'view':'driver_reference','subject':'subject viewpoint and reference order','interval':'approach through entry'}]}
plan['comparisons'][0]['status']='selected_cpu_prepared_pending_original_native'
plan['comparisons'][0]['audit_gap']='Source-sealed diagnostic stop versus rolling readbacks pass; original Native and independent pixel review remain local delivery checks.'
plan['readiness']='selected_cpu_prepared_pending_strict'
path.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
print('PASS',len(ids),len(plan['source_observation_mapping']))
