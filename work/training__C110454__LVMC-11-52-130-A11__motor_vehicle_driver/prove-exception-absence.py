"""Controlled saved-source checks for all six LVMC exception polarities."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
RETAINED=HERE/'exception-polarity-sources'
sys.path.insert(0,str(HERE/'native'))
from exception_case import BRANCHES,CITED_DEVICE_LAW_ID,CITED_DEVICE_LAW_SHA256,inspect_case


def write(path,packet):
    path.write_text(json.dumps(packet,sort_keys=True)+'\n')

def negative(path,suffix,frames,packet,change,expected):
    mutated=json.loads(json.dumps(packet))
    change(mutated)
    write(path,mutated)
    try:inspect_case(path,suffix,frames)
    except ValueError as error:
        if expected not in str(error):raise
        return str(error)
    raise ValueError('Controlled negative unexpectedly passed: '+suffix)

def main():
    frames=list(range(1000,1480));rows=[]
    RETAINED.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=HERE.parents[1]/'.runtime-work',prefix='c110454-exception-absence-') as temp:
        root=Path(temp);source=root/'exception_context.json'
        (root/'parking.mkv').write_bytes(b'synthetic device pixel source, never original CARLA pixels')
        actor=[{'native_frame':frame,'conflict_occupancy':index==220}
               for index,frame in enumerate(frames)]
        (root/'other_actor_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in actor))
        for suffix,(branch,polarity) in BRANCHES.items():
            packet={'source_kind':'native_context_schema','branch':branch,
                'requested_polarity':polarity,'original_frames':frames,
                'observed_exception_source_ids':[],'synthetic_diagnostic':True}
            if polarity=='present':
                packet['observed_exception_source_ids']=['synthetic-source']
                if branch=='necessary_traffic_conflict':
                    packet.update(other_actor_frames=[220,221],ego_brake_frames=[221],
                        intersection_boundary_source='native_map_readback')
                elif branch=='compliance_with_law':
                    packet.update(cited_law_id=CITED_DEVICE_LAW_ID,
                        cited_law_text_sha256=CITED_DEVICE_LAW_SHA256,
                        ego_action_frames=[221])
                else:
                    packet.update(original_pixel_sha256=hashlib.sha256((root/'parking.mkv').read_bytes()).hexdigest(),
                        direction_source_id='synthetic-device',direction_frame=221,
                        ego_action_frames=[221])
            write(source,packet)
            passed=inspect_case(source,suffix,frames)
            if passed['physical_observation_claimed'] is not False:
                raise ValueError('Synthetic polarity claimed physical observation')
            retained=RETAINED/suffix
            retained.mkdir(exist_ok=True)
            shutil.copy2(source,retained/'exception_context.json')
            if polarity=='present' and branch=='necessary_traffic_conflict':
                shutil.copy2(root/'other_actor_history.jsonl',retained/'other_actor_history.jsonl')
            if polarity=='present' and branch=='police_or_device_direction':
                (retained/'parking-pixels.hex').write_text((root/'parking.mkv').read_bytes().hex()+'\n')
            retained_sha=hashlib.sha256((retained/'exception_context.json').read_bytes()).hexdigest()
            if polarity=='absent':
                error=negative(source,suffix,frames,packet,
                    lambda p:p.update(observed_exception_source_ids=['source-present']),
                    'Absent exception inventory contains a source')
            elif branch=='necessary_traffic_conflict':
                actor_file=root/'other_actor_history.jsonl';original=actor_file.read_text()
                actor_file.write_text(''.join(json.dumps({'native_frame':frame,'conflict_occupancy':False})+'\n' for frame in frames))
                try:
                    inspect_case(source,suffix,frames)
                except ValueError as problem:
                    if 'Conflict source does not match' not in str(problem):raise
                    error=str(problem)
                else:raise ValueError('Conflict history negative passed')
                actor_file.write_text(original)
            elif branch=='compliance_with_law':
                error=negative(source,suffix,frames,packet,
                    lambda p:p.update(cited_law_text_sha256='0'*64),
                    'Cited law differs from frozen')
            else:
                error=negative(source,suffix,frames,packet,
                    lambda p:p.update(original_pixel_sha256='0'*64),
                    'Direction original video hash differs')
            write(source,packet)
            joined=negative(source,suffix,frames,packet,
                lambda p:p['original_frames'].pop(),
                'Exception context is not joined')
            rows.append({'case_suffix':suffix,'branch':branch,'polarity':polarity,
                'positive_source_path':str((retained/'exception_context.json').relative_to(HERE)),
                'positive_source_sha256':retained_sha,
                'controlled_negative_error':error,'truncated_frame_negative_error':joined,
                'physical_observation_claimed':False,'legal_verdict':None})
    return {'format':'lvmc-exception-polarity-source-proof-v1','passed':True,'rows':rows,
        'scope':'synthetic saved-source sufficiency and absence inventory; independent applicability and original physical observations pending'}

if __name__=='__main__':print(json.dumps(main(),indent=2))
