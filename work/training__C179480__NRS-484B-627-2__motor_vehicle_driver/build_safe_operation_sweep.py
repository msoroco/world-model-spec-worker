"""Source-shaped CPU hazard-gap samples; no safety-necessity judgment."""
import copy
import hashlib
import json
from pathlib import Path

from source_measurement import analyze_hazard

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'fixtures/safe_operation_stop-sources'
OUTPUT = HERE.parents[1] / '.runtime-work/c179480-safe-operation-sweep'
GAPS = (6.0, 8.0, 10.0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def construct(rows, gap_m):
    if gap_m not in GAPS:
        raise ValueError('Unreviewed hazard gap setting')
    if len(rows) != 600 or any(row.get('source_kind') != 'synthetic_native_sample' for row in rows):
        raise ValueError('Expected 600 source-labeled diagnostic frames')
    output = copy.deepcopy(rows)
    for original, row in zip(rows, output):
        state = row.get('hazard_state')
        if not isinstance(state, dict) or state.get('source_kind') != 'synthetic_native_sample':
            raise ValueError('Source hazard state missing')
        old_gap = state.get('ego_center_gap_m')
        if type(old_gap) not in (int, float) or old_gap <= 0:
            raise ValueError('Source hazard gap invalid')
        dx = gap_m - old_gap
        revised = row['hazard_state']
        revised['position_xyz_m'][0] = round(state['position_xyz_m'][0] + dx, 6)
        revised['body_vertices_xyz_m'] = [
            [round(vertex[0] + dx, 6), vertex[1], vertex[2]]
            for vertex in state['body_vertices_xyz_m']]
        revised['ego_center_gap_m'] = gap_m
        revised['sweep_source_kind'] = 'synthetic_placement_probe'
        revised['hazard_gap_setting_m'] = gap_m
        if abs(revised['position_xyz_m'][0] - original['ego_x_m'] - gap_m) > 1e-5:
            raise ValueError('Hazard source gap and position disagree')
    return output


def build():
    actor = SOURCE/'native-actors.jsonl'
    frame_map = SOURCE/'video_frames.jsonl'
    rows = [json.loads(line) for line in actor.read_text().splitlines()]
    probes = []
    for gap in GAPS:
        folder = OUTPUT/('gap-'+str(gap).replace('.', '_'))
        folder.mkdir(parents=True, exist_ok=True)
        sampled = folder/'native-actors.jsonl'
        sampled.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n'
                                   for row in construct(rows, gap)))
        mapping = folder/'video_frames.jsonl'
        mapping.write_bytes(frame_map.read_bytes())
        measurement = analyze_hazard(sampled, mapping, source_kind='synthetic_native_sample')
        if (measurement['sample_count'] != 600 or
                measurement['minimum_ego_center_gap_m'] != gap or
                not measurement['hazard_on_driving_lane_all_frames'] or
                measurement['safe_operation_necessity'] != 'independent_original_source_review_required'):
            raise ValueError('Hazard measurement did not preserve the planned source question')
        probes.append({'hazard_gap_setting_m':gap, 'actor_source_sha256':sha(sampled),
                       'frame_map_sha256':sha(mapping),
                       'measured_minimum_ego_center_gap_m':measurement['minimum_ego_center_gap_m'],
                       'safe_operation_necessity':measurement['safe_operation_necessity']})
    if len({row['actor_source_sha256'] for row in probes}) != 3:
        raise ValueError('Hazard settings lack distinct source histories')
    return {'format':'c179480-safe-operation-engineering-probe-v1',
            'assignment_id':HERE.name, 'passed':True,
            'source_actor_sha256':sha(actor),'source_frame_map_sha256':sha(frame_map),
            'sample_rate_hz':20,'duration_s':30,'probe_rows':probes,
            'original_native_observed':False,'physical_or_legal_acceptance_claimed':False,
            'scope':'synthetic 600-frame hazard geometry samples; no legal necessity threshold or selected case'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2, sort_keys=True))
