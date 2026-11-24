"""Independent 1,200-row audit of facing-red pedestrian entry drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FROZEN=ROOT/'inputs'/HERE.name/'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen=json.loads(FROZEN.read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    proof=json.loads((HERE/'red-entry-source-proof.json').read_text())
    manifest=json.loads((HERE/'native/draft-execution-manifest.json').read_text())
    context=json.loads((HERE/'diagnostic-red-entry/context.json').read_text())
    if (frozen['law']['text']!=plan['source_law']['text'] or
            frozen['cell']['cell_id']!='C111331' or
            len(plan['cases'])!=2 or len(manifest['cases'])!=2 or
            len(proof['records'])!=2 or len(proof['negative_rejections'])!=6 or
            not proof['passed'] or manifest['delivery_ready']):
        raise ValueError('Red-entry scope or pair incomplete')
    face_dot=sum(a*b for a,b in zip(context['signal_face_vector_xy'],
                                    context['pedestrian_approach_vector_xy']))
    if face_dot<=0 or context['signal_authority_native_verified']:
        raise ValueError('Pedestrian signal facing/authority invalid')
    sources=[]
    for index,condition in enumerate(('condition_a','condition_b')):
        source=HERE/'diagnostic-red-entry'/(condition+'.jsonl')
        rows=[json.loads(line) for line in source.read_text().splitlines()]
        if len(rows)!=600 or sha(source)!=proof['records'][index]['source_sha256']:
            raise ValueError('Retained source binding changed')
        item=manifest['cases'][index]
        if (item['case_id']!=plan['cases'][index]['case_id'] or
                sha(HERE/'native'/item['construction'])!=item['construction_sha256']):
            raise ValueError('Offline construction binding changed')
        entry=[]
        for frame,row in enumerate(rows):
            if (row['frame']!=frame or row['time_s']!=frame/20 or
                    row['signal_state']!='steady_red_alone' or
                    row['signal_id']!=context['signal_id'] or
                    row['other_device_id'] is not None or
                    row['other_device_permits'] or
                    row['original_native_observed'] or row['legal_verdict'] is not None):
                raise ValueError('Signal state, exception or frame changed')
            if min(point[1] for point in row['pedestrian_footprint_xy_m'])<2.0:
                entry.append(frame)
        expected_first=min(entry) if entry else None
        if expected_first!=proof['records'][index]['first_highway_footprint_frame']:
            raise ValueError('Footprint entry measurement disagrees')
        sources.append(rows)
    a,b=sources
    fixed=set(a[0])-{'pedestrian_center_xy_m','pedestrian_footprint_xy_m','requested_entry_condition'}
    if any({k:x[k] for k in fixed}!={k:y[k] for k in fixed} for x,y in zip(a,b)):
        raise ValueError('Comparison fixed conditions changed')
    if (proof['records'][0]['first_highway_footprint_frame'] is not None or
            proof['records'][1]['first_highway_footprint_frame'] is None or
            proof['other_device_exception_tested']):
        raise ValueError('Entry contrast or exception status wrong')
    result={'format':'c111331-independent-red-entry-audit-v1','passed':True,
            'frozen_assignment_sha256':sha(FROZEN),
            'source_proof_sha256':sha(HERE/'red-entry-source-proof.json'),
            'draft_manifest_sha256':sha(HERE/'native/draft-execution-manifest.json'),
            'context_sha256':sha(HERE/'diagnostic-red-entry/context.json'),
            'frames_per_condition':600,'rate_hz':20,
            'first_highway_footprint_frame':proof['records'][1]['first_highway_footprint_frame'],
            'controlled_variable':'pedestrian_highway_entry',
            'other_device_exception_tested':False,
            'native_signal_authority_verified':False,
            'legal_verdict_claimed':False}
    target=HERE/'red-entry-independent-audit.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'audit_sha256':sha(target),
                      'first_entry_frame':result['first_highway_footprint_frame']}))


if __name__=='__main__':
    main()
