"""Independently check held conditions and declared diagnostic differences."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PAIRS=(('reference','contrast','draft-execution-manifest.json','lateral'),
       ('rail_reference','rail_contrast','draft-statutory-execution-manifest.json','lateral'),
       ('oneway_absent','oneway_present','draft-statutory-execution-manifest.json','designation'),
       ('traversal_reference','traversal_contrast','draft-traversal-execution-manifest.json','lateral_traversal'))


def require(ok,message):
    if not ok:raise ValueError(message)


def rows(text):return [json.loads(line) for line in text.splitlines() if line.strip()]


def construction(manifest,suffix):
    entry=next(row for row in manifest['cases'] if row['case_id']==HERE.name+'__'+suffix)
    raw=json.loads((HERE/entry['construction']).read_text())
    files={row['path']:row['content'] for row in raw['files']}
    return json.loads(files['config.json']),files


def audit():
    result=[]
    plan=json.loads((HERE/'case-plan.json').read_text())
    comparisons={row['comparison_id']:row for row in plan['comparisons']}
    for a,b,manifest_name,kind in PAIRS:
        comparison_id=HERE.name+'__comparison_'+(
            'main' if a=='reference' else 'rail' if a=='rail_reference' else
            'oneway' if a=='oneway_absent' else 'traversal')
        comparison=comparisons[comparison_id]
        require(comparison['case_ids']==[HERE.name+'__'+a,HERE.name+'__'+b],
                'Frozen controlled pair differs')
        manifest=json.loads((HERE/manifest_name).read_text())
        ca,fa=construction(manifest,a);cb,fb=construction(manifest,b)
        identity={'case_id','selected_case_id','supported_case_ids','case','case_suffix'}
        require({k:v for k,v in ca.items() if k not in identity}==
                {k:v for k,v in cb.items() if k not in identity},
                'Held exact construction config differs')
        sa=json.loads((HERE/f'update015-{a}-diagnostic.json').read_text())
        sb=json.loads((HERE/f'update015-{b}-diagnostic.json').read_text())
        require(sa['videos']==sb['videos'] and
                sa['files']['capture/recorder_info.txt']==sb['files']['capture/recorder_info.txt'],
                'Held four-camera capture policy differs')
        ra=json.loads(sa['files']['road_geometry.json']);rb=json.loads(sb['files']['road_geometry.json'])
        xa=rows(sa['files']['native_samples.jsonl']);xb=rows(sb['files']['native_samples.jsonl'])
        ea=rows(sa['files']['capture/evidence.jsonl']);eb=rows(sb['files']['capture/evidence.jsonl'])
        require(len(xa)==len(xb)==len(ea)==len(eb)==480 and
                all(x['native_center_xy_m'][0]==y['native_center_xy_m'][0]
                    for x,y in zip(xa,xb)) and
                all(x['world']['weather']==y['world']['weather'] for x,y in zip(ea,eb)),
                'Held longitudinal schedule or weather differs')
        lateral=sum(x['native_center_xy_m'][1]!=y['native_center_xy_m'][1]
                    for x,y in zip(xa,xb))
        speed=sum(x['speed_m_s']!=y['speed_m_s'] for x,y in zip(xa,xb))
        if kind=='designation':
            changed={key for key in ra if ra[key]!=rb[key]}
            require(changed=={'road_directions_native','one_way_native_readback'} and
                    ra['one_way_native_readback'] is False and rb['one_way_native_readback'] is True and
                    lateral==speed==0 and fa['road.xodr']!=fb['road.xodr'],
                    'One-way comparison changes more than designation')
        else:
            require(ra==rb and lateral>0,'Lateral controlled difference absent')
            if 'road.xodr' in fa:
                require(fa['road.xodr']==fb['road.xodr'],'Held authored road differs')
            else:
                require(sa['files']['road.xodr']==sb['files']['road.xodr'],
                        'Held diagnostic road differs')
            if kind=='lateral':
                require(speed==0,'Approach speed schedule differs')
            else:
                require(a=='traversal_reference' and speed>0 and
                        xa[-1]['native_center_xy_m']==xb[-1]['native_center_xy_m'] and
                        'commanded speed policy' in comparison['fixed_conditions'],
                        'Traversal speed consequence not disclosed')
        result.append({'comparison_id':comparison_id,'cases':[a,b],
                       'lateral_changed_frames':lateral,
                       'sampled_speed_changed_frames':speed,
                       'declared_difference':comparison['deliberate_differences']})
    return {'controlled_pairs_checked':len(result),'pairs':result,
            'scope':'unselected synthetic source comparison; no physical or legal acceptance'}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
