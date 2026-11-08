"""Independent raw-row and exact-bundle audit of the no-entry control."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=HERE/'no-entry-sources'
    saved=json.loads((HERE/'no-entry-saved-proof.json').read_text())
    offline=json.loads((HERE/'no-entry-offline-proof.json').read_text())
    manifest_path=HERE/'draft-no-entry-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry=manifest['cases'][0]
    if (saved.get('passed') is not True or offline.get('passed') is not True or
        saved['manifest_sha256']!=sha(manifest_path) or
        offline['manifest_sha256']!=sha(manifest_path) or
        len(saved['candidates'])!=4 or len(offline['candidates'])!=4):
        raise ValueError('No-entry exact proof or manifest differs')
    if set(saved['source_sha256'])!={'native_samples.jsonl','road_geometry.json','entry-sources.json'}:
        raise ValueError('No-entry source inventory differs')
    if any(sha(source/name)!=value for name,value in saved['source_sha256'].items()):
        raise ValueError('No-entry retained source hash differs')
    geometry=json.loads((source/'road_geometry.json').read_text())
    bounds=geometry['bicycle_facility_native_xy_bounds_m']
    rows=[json.loads(line) for line in (source/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480 or rows[0]['native_center_xy_m']!=[-45.0,-1.5] or \
       rows[-1]['native_center_xy_m']!=[15.0,-1.5]:
        raise ValueError('No-entry source path endpoints differ')
    areas=[]
    for index,row in enumerate(rows):
        if (row['native_frame']!=1000+index or abs(row['time_s']-(index+1)*.05)>1e-5 or
            row['native_lane_id']!=geometry['driving_lane_id'] or
            row['native_road_id']!=geometry['road_id'] or
            row.get('synthetic_diagnostic') is not True):
            raise ValueError('No-entry original-frame or provenance contract differs')
        body=row['native_body_xy_m'];center=row['native_center_xy_m']
        if abs(sum(v[0] for v in body)/4-center[0])>1e-4 or \
           abs(sum(v[1] for v in body)/4-center[1])>1e-4:
            raise ValueError('No-entry body/center source differs')
        left=max(min(v[0] for v in body),bounds[0]);right=min(max(v[0] for v in body),bounds[2])
        bottom=max(min(v[1] for v in body),bounds[1]);top=min(max(v[1] for v in body),bounds[3])
        areas.append(max(0,right-left)*max(0,top-bottom))
    if max(areas)>1e-9 or any(row['speed_mps']<=.1 for row in rows):
        raise ValueError('Independent no-entry moving body intersects facility')
    comparison=json.loads((HERE/'no-entry-comparison-proof.json').read_text())
    crossing_root=HERE/'no-entry-comparison-sources'/'entry'
    if (comparison.get('passed') is not True or comparison.get('selected') is not False or
        len(comparison.get('candidate_pairs',[]))!=4 or
        any(sha(crossing_root/name)!=digest for name,digest in comparison['entry_source_sha256'].items()) or
        sha(crossing_root/'road_geometry.json')!=sha(source/'road_geometry.json')):
        raise ValueError('Controlled entry source or proof differs')
    crossing=[json.loads(line) for line in (crossing_root/'native_samples.jsonl').read_text().splitlines()]
    if len(crossing)!=480:
        raise ValueError('Controlled entry frame count differs')
    entry_areas=[]
    for a,b in zip(rows,crossing):
        if (a['native_frame']!=b['native_frame'] or a['time_s']!=b['time_s'] or
            a['native_center_xy_m'][0]!=b['native_center_xy_m'][0] or
            a['speed_mps']!=b['speed_mps'] or
            a['native_road_id']!=b['native_road_id']):
            raise ValueError('Controlled pair changed fixed longitudinal/time inputs')
        body=b['native_body_xy_m'];center=b['native_center_xy_m']
        if abs(sum(v[0] for v in body)/4-center[0])>1e-4 or \
           abs(sum(v[1] for v in body)/4-center[1])>1e-4:
            raise ValueError('Controlled entry body/center differs')
        left=max(min(v[0] for v in body),bounds[0]);right=min(max(v[0] for v in body),bounds[2])
        bottom=max(min(v[1] for v in body),bounds[1]);top=min(max(v[1] for v in body),bounds[3])
        entry_areas.append(max(0,right-left)*max(0,top-bottom))
    first=next((i for i in range(1,480) if entry_areas[i-1]<=.01 and entry_areas[i]>.01),None)
    occupied=sum(area>.01 for area in entry_areas)
    if first is None or occupied<=0:
        raise ValueError('Independent controlled entry was not measured')
    for candidate,save_row,offline_row in zip(NAMES,saved['candidates'],offline['candidates']):
        ref=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
        construction=HERE/ref['construction']
        unit=HERE/'draft-no-entry-candidates'/'probe_d_no_entry'/candidate/'unit-test.log'
        command=unit.parent/'offline.log'
        if (save_row['candidate']!=candidate or offline_row['candidate']!=candidate or
            save_row['construction_sha256']!=sha(construction) or
            offline_row['construction_sha256']!=sha(construction) or
            ref['construction_sha256']!=sha(construction) or
            offline_row['unit_log_sha256']!=sha(unit) or
            offline_row['log_sha256']!=sha(command) or
            offline_row['exit_code']!=0 or offline_row['passed_tests']!=4 or
            save_row['moving_entry_measured'] is not False or
            save_row['moving_occupied_frames']!=0 or
            'entry-sources.json' not in save_row['missing_source_negative'] or
            'Entry source hash differs' not in save_row['changed_byte_negative']):
            raise ValueError('No-entry candidate offline/saved receipt differs')
        files=json.loads(construction.read_text())['files']
        meter=[f['content'] for f in files if f['path']=='measure_entry.py']
        if len(meter)!=1 or hashlib.sha256(meter[0].encode()).hexdigest()!=save_row['meter_sha256']:
            raise ValueError('No-entry exact saved meter differs')
        pair_row=comparison['candidate_pairs'][NAMES.index(candidate)]
        if (pair_row['candidate']!=candidate or
            pair_row['construction_sha256']!=sha(construction) or
            pair_row['meter_sha256']!=save_row['meter_sha256'] or
            pair_row['no_entry_moving_frames']!=0 or
            pair_row['entry_moving_frames']!=occupied or
            pair_row['first_entry_native_frame']!=crossing[first]['native_frame']):
            raise ValueError('Controlled exact candidate pair receipt differs')
    return {'format':'c10052-no-entry-independent-audit-v1','passed':True,
            'frames':len(rows),'maximum_moving_overlap_m2':max(areas),
            'controlled_entry_frames':occupied,
            'first_controlled_entry_native_frame':crossing[first]['native_frame'],
            'exact_candidates':list(NAMES),'selected':False,
            'physical_or_legal_verdict_claimed':False}


if __name__=='__main__':
    result=main()
    (HERE/'no-entry-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
