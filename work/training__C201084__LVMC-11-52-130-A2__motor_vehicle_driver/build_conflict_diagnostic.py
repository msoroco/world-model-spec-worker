"""Derive a labelled lead-traffic CPU fixture from retained synthetic sources."""
import argparse
import json
import shutil
from pathlib import Path
from conflict_controller import decision


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if '.runtime-work' not in source.parts or '.runtime-work' not in output.parts:
        raise ValueError('Diagnostic source and output must stay under .runtime-work')
    if output.exists():
        raise ValueError('Retain prior diagnostic output; choose a fresh directory')
    output.mkdir(parents=True)
    for name in ('video_frames.jsonl', *[camera+'.mkv' for camera in CAMERAS]):
        shutil.copyfile(source/name, output/name)
    provenance = json.loads((source/'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'synthetic_fixture' or \
            provenance.get('diagnostic_fixture') is not True:
        raise ValueError('Source is not an explicitly synthetic fixture')
    (output/'acquisition-provenance.json').write_text(
        json.dumps(provenance, indent=2)+'\n')
    plan = json.loads((source/'native-survey-readback.json').read_text())
    plan['conflict_probe'] = {
        'lead_spawn_xy_m': [18, 1],
        'lead_blueprint': 'vehicle.lincoln.mkz_2017',
        'statutory_necessity_verified': False,
        'original_review_required': True}
    (output/'native-survey-readback.json').write_text(
        json.dumps(plan, indent=2)+'\n')
    actors = [json.loads(line) for line in
              (source/'native-actors.jsonl').read_text().splitlines()]
    if len(actors) != 600 or any(
            actor.get('source_kind') != 'synthetic_native_sample'
            for actor in actors):
        raise ValueError('Expected 600 explicitly synthetic source rows')
    for actor in actors:
        requested = decision(actor['ego_pose_xyz_m'][:2],
                             actor['ego_velocity_xyz_mps'][:2],
                             [18, 1], [0, 0],
                             actor['ego_yaw_deg'])
        actor.update(lead_actor_id=77, lead_road_id=17, lead_lane_id=-1,
            lead_pose_xyz_m=[18, 1, 0], lead_yaw_deg=0,
            lead_velocity_xyz_mps=[0, 0, 0],
            lead_body_vertices_xyz_m=[[17, 0, 0], [19, 0, 0],
                                      [19, 2, 0], [17, 2, 0]],
            requested_control=requested,
            physical_completion_claimed=False,
            statutory_necessity_claimed=False)
    (output/'native-actors.jsonl').write_text(''.join(
        json.dumps(actor, allow_nan=False)+'\n' for actor in actors))
    reference = json.loads((HERE/'draft-reference-construction.json').read_text())
    config = json.loads(next(row['content'] for row in reference['files']
                             if row['path'] == 'config.json'))
    case = ASSIGNMENT+'__conflict'
    config.update(case_id=case, selected_case_id=case,
                  case_suffix='conflict', candidate_id='primary')
    config['recording_description']['channels'].append({
        'name': 'lead_traffic_relation', 'unit': 'm',
        'sampling_rate_hz': 20,
        'reference_frame': 'original CARLA ego heading and lead actor',
        'time_window': 'all 600 frames / 30 seconds',
        'method': 'source_measurement from retained ego and lead actor rows',
        'uncertainty': '50 ms sample clock; statutory necessity requires review'})
    (output/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    return {'case_id': case, 'source_frames': len(actors),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == '__main__':
    main()
