"""Independent CPU comparison of the clear and nearer backing source plans."""
from hashlib import sha256
import json
from pathlib import Path

STAGE=Path(__file__).resolve().parent
PREFIX='heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__'

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def rows(value):return [json.loads(line) for line in value.splitlines() if line.strip()]

def check(clear,near,clear_receipt,near_receipt):
    a=json.loads(json.dumps(clear));b=json.loads(json.dumps(near))
    if set(a['files'])!=set(b['files']):raise ValueError('Comparison source inventory differs')
    primary=PREFIX+'backing_clear_vehicle';secondary=PREFIX+'backing_near_vehicle'
    for spec,case in ((a,primary),(b,secondary)):
        capture=json.loads(spec['files']['capture/manifest.json'])
        if capture.get('case_id')!=case:raise ValueError('Comparison capture identity differs')
        capture['case_id']='CONTROLLED_CASE'
        spec['files']['capture/manifest.json']=json.dumps(capture,sort_keys=True)
        corridor=json.loads(spec['files']['backing_corridor_original.json'])
        other=corridor.pop('other_vehicle_xy')
        corridor.pop('note',None)
        spec['files']['backing_corridor_original.json']=json.dumps(corridor,sort_keys=True)
        context=json.loads(spec['files']['backing_context.json'])
        context.pop('corridor_source_sha256')
        spec['files']['backing_context.json']=json.dumps(context,sort_keys=True)
        motion=rows(spec['files']['backing_motion.jsonl'])
        for row in motion:row['participants']['20'].pop('x_m')
        spec['files']['backing_motion.jsonl']=json.dumps(motion,sort_keys=True)
        spec['_other_start_x']=other[0]
    clear_x=a.pop('_other_start_x');near_x=b.pop('_other_start_x')
    if a!=b:raise ValueError('Undeclared source or fixed condition changed')
    if not (near_x>clear_x and abs(clear_x-8.0)<1e-9 and abs(near_x-9.5)<1e-9):
        raise ValueError('Declared narrower other-vehicle start position differs')
    for receipt,case in ((clear_receipt,primary),(near_receipt,secondary)):
        if receipt.get('case_id')!=case or receipt.get('candidate_id')!='primary' or receipt.get('passed') is not True:
            raise ValueError('Comparison exact compatibility receipt differs')
    def value(receipt):return receipt['measurement_examples']['backing_safety_observation']['value']
    old,new=value(clear_receipt),value(near_receipt)
    if old['backing_onset_frame']!=new['backing_onset_frame'] or old['backing_end_frame']!=new['backing_end_frame']:
        raise ValueError('Fixed ego backing interval changed')
    old_gap=old['minimum_surface_gap_during_backing_m']['20']
    new_gap=new['minimum_surface_gap_during_backing_m']['20']
    if not new_gap<old_gap:raise ValueError('Declared narrower measured clearance absent')
    if old['contact_frames_during_backing']!=new['contact_frames_during_backing']:
        raise ValueError('Undeclared contact packet difference')
    return {'format':'worker-comparison-cpu-audit','comparison_id':'clearance_safety',
            'case_ids':[primary,secondary],'fixed_sources_equal_after_declared_difference':True,
            'clear_minimum_surface_gap_m':old_gap,'near_minimum_surface_gap_m':new_gap,
            'measured_clearance_narrower':True,'legal_safety_claimed':False,'physical_acceptance_claimed':False}

if __name__=='__main__':
    result=check(load(STAGE/'diagnostic-first-primary.json'),load(STAGE/'diagnostic-near-vehicle.json'),
                 load(STAGE/'compat-clear-primary-two/compatibility.json'),load(STAGE/'compat-near-primary/compatibility.json'))
    print(json.dumps(result,indent=2))
