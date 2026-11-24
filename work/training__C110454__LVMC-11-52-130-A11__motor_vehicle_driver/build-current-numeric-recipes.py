"""Construct source-bound 600-frame numeric diagnostics from exact authored routes."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMPLATE=HERE/'current-v2-source/witness_2'
BASE=json.loads((HERE/'current-v2-witness_2-recipe.json').read_text())
GENERATOR=json.loads((HERE/'current-v2-witness_2-generator.json').read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))


def main():
    for suffix in ('numeric_1_1','numeric_1_2'):
        route=json.loads((HERE/'native/routes'/f'{suffix}.json').read_text())
        target=HERE/'current-v2-numeric-source'/suffix
        names=('native_samples.jsonl','native_parking_history.json','trace.jsonl',
               'body_history.jsonl','capture/evidence.jsonl','capture/manifest.json')
        samples=read_rows(TEMPLATE/'native_samples.jsonl')
        trace=read_rows(TEMPLATE/'trace.jsonl')
        body=read_rows(TEMPLATE/'body_history.jsonl')
        evidence=read_rows(TEMPLATE/'capture/evidence.jsonl')
        parking=json.loads((TEMPLATE/'native_parking_history.json').read_text())
        generator=copy.deepcopy(GENERATOR)
        assert len(samples)==len(trace)==len(body)==len(evidence)==len(generator['graphs'])==600
        for i in range(600):
            index=min(round(i*(len(route)-1)/519),len(route)-1)
            x,y=route[index]
            if i>=520:
                fx,fy=1.0,0.0
            else:
                left=route[max(index-1,0)];right=route[min(index+1,len(route)-1)]
                dx=right[0]-left[0];dy=right[1]-left[1];length=math.hypot(dx,dy)
                fx,fy=(dx/length,dy/length) if length else (1.0,0.0)
            rx,ry=-fy,fx
            corners=[[x+direction*2.6*fx+side*1.1*rx,
                      y+direction*2.6*fy+side*1.1*ry]
                     for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
            vertices=[[a,b,z] for a,b in corners for z in (0,1.5)]
            sample=samples[i]
            sample['native_center_xy_m']=[x,y]
            sample['native_forward_xy']=[fx,fy]
            sample['native_body_xy_m']=corners
            sample['body_xy_m']=corners
            parking['frames'][i]['body_xy_m']=corners
            row=trace[i]
            row['position']={'x':x,'y':y,'z':0.5}
            row['position_m']=[x,y,0.5]
            row['heading_deg']=math.degrees(math.atan2(fy,fx))
            row['velocity_mps']=[sample['speed_m_s']*fx,sample['speed_m_s']*fy,0.0]
            body[i]['body_vertices_m']=vertices
            ego=evidence[i]['ego']
            ego['body_vertices_m']=vertices
            ego['position_m']=[x,y,0.5]
            ego['heading_deg']=row['heading_deg']
            graph=generator['graphs'][i]['nodes'][0]['attributes']
            graph['vertex']=[x,y,0.5]
            graph['forward']=[fx,fy,0.0]
        write_rows(target/'native_samples.jsonl',samples)
        write_rows(target/'trace.jsonl',trace)
        write_rows(target/'body_history.jsonl',body)
        write_rows(target/'capture/evidence.jsonl',evidence)
        (target/'native_parking_history.json').write_text(json.dumps(parking,separators=(',',':'))+'\n')
        capture=json.loads((TEMPLATE/'capture/manifest.json').read_text())
        capture['sources']['trace.jsonl']=sha(target/'trace.jsonl')
        (target/'capture/manifest.json').parent.mkdir(parents=True,exist_ok=True)
        (target/'capture/manifest.json').write_text(json.dumps(capture,separators=(',',':'))+'\n')
        spec=HERE/f'current-v2-{suffix}-generator.json'
        spec.write_text(json.dumps(generator,separators=(',',':'))+'\n')
        recipe=copy.deepcopy(BASE)
        source_map={x['path']:x for x in recipe['sources']}
        for name in names:
            source_map[name]={'path':name,'source':str((target/name).relative_to(ROOT)),'sha256':sha(target/name)}
        recipe['sources']=list(source_map.values())
        recipe['generator']={'source':str(spec.relative_to(ROOT)),'sha256':sha(spec)}
        path=HERE/f'current-v2-{suffix}-recipe.json'
        path.write_text(json.dumps(recipe,indent=2)+'\n')
        assert max((target/name).stat().st_size for name in names)<2*1024*1024
        print(suffix,sha(path),len(route),route[-1])

if __name__=='__main__':
    main()
